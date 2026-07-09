# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Local system integration test runner for local emulated stack testing.

This script uses Pytest to verify database schema initialization, database
seeding, and semantic query serving endpoints against emulators. It uses
the requests library for standard HTTP client operations.
"""

import difflib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import grpc
import pytest
import requests
from google.cloud import spanner

# Import patch_credentials to apply Spanner emulator monkeypatches to the host-side test runner
sys.path.append(str(Path(__file__).resolve().parent))
import patch_credentials  # noqa: F401

# =============================================================================
# Parameterized Configuration Constants
# =============================================================================


def get_port(env_var: str, default: int) -> int:
    val = os.getenv(env_var)
    if val:
        return int(val)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", default))
            return default
        except OSError:
            # Default port is busy; allocate a dynamic free port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                s2.bind(("", 0))
                return s2.getsockname()[1]


WEBSITE_PORT = get_port("WEBSITE_PORT", 8082)
HELPER_PORT = get_port("HELPER_PORT", 8081)
SPANNER_REST_PORT = get_port("SPANNER_REST_PORT", 9020)
SPANNER_GRPC_PORT = get_port("SPANNER_GRPC_PORT", 9010)
MOCK_NL_PORT = get_port("MOCK_NL_PORT", 6060)

PROJECT_ID = os.getenv("SPANNER_PROJECT_ID", "default")
INSTANCE_ID = os.getenv("SPANNER_INSTANCE_ID", "default")
DATABASE_ID = os.getenv("SPANNER_DATABASE_ID", "test-db")

# =============================================================================
# Helper Utilities
# =============================================================================


def run_command(
    args: list[str],
    cwd: Path | None = None,
    *,
    check: bool = True,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(  # noqa: S603
            args, cwd=cwd, check=check, text=True, env=env, capture_output=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(args)}", file=sys.stderr)
        if e.stdout:
            print(f"Stdout:\n{e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"Stderr:\n{e.stderr}", file=sys.stderr)
        raise e


def check_docker_environment() -> None:
    """Checks if Docker is installed and the Docker daemon is running."""
    try:
        # Run docker info to verify that the docker command is available
        # and that the daemon is responsive.
        res = subprocess.run(  # noqa: S603
            ["docker", "info"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            err_msg = (
                "ERROR: Docker daemon is not running or not reachable.\n"
                "Please start Docker Desktop or ensure the Docker service is running."
            )
            if res.stderr:
                err_msg += f"\nDetails:\n{res.stderr.strip()}"
            pytest.exit(err_msg, returncode=1)
    except FileNotFoundError:
        pytest.exit(
            "ERROR: 'docker' CLI not found.\n"
            "Please install Docker (e.g. Docker Desktop) before running integration tests.",
            returncode=1,
        )


def wait_for_service(
    url: str,
    name: str,
    method: str = "GET",
    expected_statuses: tuple[int, ...] = (200,),
    timeout_secs: int = 30,
) -> None:
    """Waits for a service to become responsive by polling the given URL."""
    print(f"Waiting for {name} to be ready at {url}...", flush=True)
    start_time = time.time()
    while time.time() - start_time < timeout_secs:
        try:
            if method == "POST":
                resp = requests.post(url, json={}, timeout=2)
            else:
                resp = requests.get(url, timeout=2)

            if resp.status_code in expected_statuses:
                print(f"  {name} is ready!", flush=True)
                return
            if resp.status_code == 502 and name == "Website":
                print(
                    "  Website proxy is up, waiting for Go/Flask backend to boot...",
                    flush=True,
                )
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"{name} failed to start within {timeout_secs} seconds.")


def call_helper(action_type: str) -> dict:
    path = (
        "database/initialize"
        if action_type == "initialize_database"
        else "database/seed"
    )
    url = f"http://localhost:{HELPER_PORT}/{path}"
    try:
        resp = requests.post(url, json={"actionType": action_type}, timeout=120)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {"status": "success", "message": resp.text}
    except Exception as e:
        raise RuntimeError(
            f"HTTP call to Ingestion Helper failed for action {action_type}: {e}"
        ) from e  # noqa: BLE001


def seed_gcs_emulator() -> None:
    """Create test-bucket and upload dummy catalog yaml and wages dataset to mock GCS emulator."""
    print(">>> Seeding fake GCS emulator bucket and catalogs...", flush=True)
    try:
        # 1. Create bucket
        resp = requests.post(
            "http://localhost:9099/storage/v1/b?project=test-project",
            json={"name": "test-bucket"},
            timeout=5,
        )
        resp.raise_for_status()

        # 2. Upload dummy custom_catalog.yaml
        dummy_catalog = "version: '1'\nmodels: {}\nindexes: {}\n"
        upload_resp = requests.post(
            "http://localhost:9099/upload/storage/v1/b/test-bucket/o?uploadType=media&name=output/datacommons/nl/embeddings/custom_catalog.yaml",
            data=dummy_catalog,
            headers={"Content-Type": "application/x-yaml"},
            timeout=5,
        )
        upload_resp.raise_for_status()

        # 3. Upload OECD wages files for local ingestion run
        wages_dir = Path(__file__).resolve().parents[2] / "samples" / "OECD_wage_data"
        files_to_upload = [
            "average_annual_wage.csv",
            "average_annual_wage.mcf",
            "gender_wage_gap.csv",
            "gender_wage_gap.mcf",
            "config.json",
        ]
        for filename in files_to_upload:
            file_path = wages_dir / filename
            with file_path.open("rb") as f:
                data = f.read()
            content_type = (
                "application/json"
                if filename.endswith(".json")
                else "application/octet-stream"
            )
            upload_resp = requests.post(
                f"http://localhost:9099/upload/storage/v1/b/test-bucket/o?uploadType=media&name=ingestion/input/wages/{filename}",
                data=data,
                headers={"Content-Type": content_type},
                timeout=5,
            )
            upload_resp.raise_for_status()

        print("  GCS emulator successfully seeded.", flush=True)
    except Exception as e:
        raise RuntimeError(f"Failed to seed GCS emulator: {e}") from e  # noqa: BLE001


# =============================================================================
# Pytest Orchestration Fixture
# =============================================================================


def wait_for_spanner(timeout_secs: int = 90) -> None:
    """Waits for Spanner gRPC endpoint to become ready."""

    import socket

    print("Waiting for Spanner gRPC endpoint to be ready...", flush=True)
    os.environ["SPANNER_EMULATOR_HOST"] = f"127.0.0.1:{SPANNER_GRPC_PORT}"
    start_time = time.time()
    while time.time() - start_time < timeout_secs:
        try:
            with socket.create_connection(
                ("127.0.0.1", SPANNER_GRPC_PORT), timeout=1
            ):
                print("  Spanner is ready!", flush=True)
                return
        except (ConnectionRefusedError, socket.timeout):
            time.sleep(0.5)
    raise RuntimeError(f"Spanner failed to start within {timeout_secs} seconds.")


def create_spanner_db() -> None:
    """Creates Spanner instance and database using client library via gRPC."""

    os.environ["SPANNER_EMULATOR_HOST"] = f"127.0.0.1:{SPANNER_GRPC_PORT}"
    print(
        f">>> Creating Spanner instance {INSTANCE_ID} and database {DATABASE_ID} via gRPC client...",
        flush=True,
    )
    client = spanner.Client(project=PROJECT_ID)
    instance = client.instance(
        INSTANCE_ID,
        configuration_name=f"projects/{PROJECT_ID}/instanceConfigs/emulator-config",
        node_count=1,
    )
    if not instance.exists():
        op = instance.create()
        op.result(timeout=30)
    database = instance.database(DATABASE_ID)
    if not database.exists():
        op = database.create()
        op.result(timeout=30)
    print("  Spanner database created.", flush=True)


def check_and_compile_java_loader_if_needed(
    import_repo_dir: str, jar_path: Path, compose_env: dict[str, str]
) -> None:
    """Detects if Java source files are newer than the compiled JAR and auto-rebuilds via Maven container."""
    pipeline_dir = Path(import_repo_dir) / "pipeline"
    if not pipeline_dir.exists():
        return

    # If JAR does not exist at all, we don't compile (we fallback to container default)
    if not jar_path.exists():
        return

    jar_mtime = jar_path.stat().st_mtime
    rebuild = False
    for path in pipeline_dir.rglob("*.java"):
        if path.stat().st_mtime > jar_mtime:
            print(
                f"  [Auto-Rebuild] Detected newer Java source: {path.name}", flush=True
            )
            rebuild = True
            break

    if rebuild:
        print(
            ">>> Java source files are newer than compiled JAR. Automatically compiling...",
            flush=True,
        )
        try:
            # We compile using Maven Docker container so no host Java installation is required
            run_command(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{import_repo_dir}:/workspace",
                    "-w",
                    "/workspace",
                    "maven:3.9.6-eclipse-temurin-17",
                    "mvn",
                    "clean",
                    "package",
                    "-pl",
                    "pipeline/ingestion",
                    "-am",
                    "-DskipTests",
                ],
                env=compose_env,
            )
            print(">>> Java auto-compilation completed successfully!", flush=True)
        except Exception as e:  # noqa: BLE001
            print(
                f"WARNING: Java auto-compilation failed. Falling back to existing JAR. Error: {e}",
                flush=True,
            )


def run_spanner_loader(compose_env: dict[str, str]) -> None:
    """Run the real Java Dataflow Spanner Loader container locally under DirectRunner."""
    print(">>> Running local Java Spanner Loader pipeline...", flush=True)

    try:
        resp = requests.get(
            "http://localhost:9099/storage/v1/b/test-bucket/o", timeout=10
        )
        resp.raise_for_status()
        items = [item["name"] for item in resp.json().get("items", [])]
    except Exception as e:
        raise RuntimeError(f"Failed to query GCS emulator: {e}") from e

    # Extract output directories like output/jsonld/<timestamp_dir>/<import_name>/
    jsonld_blobs = [
        name for name in items if "output/jsonld/" in name and name.endswith(".jsonld")
    ]
    import_dirs = set()
    for name in jsonld_blobs:
        parts = name.split("/")
        if len(parts) >= 5:
            import_dirs.add("/".join(parts[:4]))

    if not import_dirs:
        raise ValueError("No generated JSON-LD files found in GCS emulator.")

    import_list = []
    for d in import_dirs:
        import_name = d.split("/")[-1]
        import_list.append(
            {"importName": import_name, "graphPath": f"gs://test-bucket/{d}/*.jsonld"}
        )

    print(f"  Found import directories: {list(import_dirs)}", flush=True)

    # Dummy PKCS8 encoded key, not used anywhere else except avoid errors.
    dummy_key = (
        "-----BEGIN"
        " FAKE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC3\n-----END"
        " FAKE KEY-----\n"
    )

    dummy_creds = {
        "type": "service_account",
        "project_id": "default",
        "private_key_id": "dummy",
        "private_key": dummy_key,
        "client_email": "dummy@default.iam.gserviceaccount.com",
        "client_id": "1234567890",
    }
    root_dir = Path(__file__).resolve().parent
    dummy_creds_path = root_dir / "dummy_credentials.json"
    with dummy_creds_path.open("w") as f:
        json.dump(dummy_creds, f)

    # Resolve the import repository directory (relative default of sibling directory)
    import_repo_dir = os.environ.get("IMPORT_REPO_DIR") or str(
        Path(__file__).resolve().parents[3] / "import"
    )
    jar_path = (
        Path(import_repo_dir)
        / "pipeline/ingestion/target/ingestion-bundled-0.1-SNAPSHOT.jar"
    )

    # Automatically check and rebuild JAR if Java files changed
    check_and_compile_java_loader_if_needed(import_repo_dir, jar_path, compose_env)

    jar_mount = []
    if jar_path.exists() and jar_path.is_file():
        print(f"  Detected local compiled Java JAR, mounting: {jar_path}", flush=True)
        jar_mount = ["-v", f"{jar_path}:/app/ingestion-bundled.jar"]
    else:
        print("  No local JAR detected. Falling back to container default.", flush=True)

    try:
        # 3. Execute the Java Beam pipeline container inside the compose network 'itest-net'
        # pointing to GCS and Spanner emulators
        cmd = [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "java",
            "--network",
            "itest-net",
            "-e",
            "GOOGLE_APPLICATION_CREDENTIALS=/app/dummy_credentials.json",
            "-e",
            "SPANNER_EMULATOR_HOST=spanner:15000",
            "-e",
            "GOOGLE_CLOUD_SPANNER_MULTIPLEXED_SESSIONS=TRUE",
            "-e",
            "GOOGLE_CLOUD_SPANNER_MULTIPLEXED_SESSIONS_FOR_RW=TRUE",
            "-v",
            f"{dummy_creds_path}:/app/dummy_credentials.json",
        ]
        if jar_mount:
            cmd.extend(jar_mount)
        cmd.extend(
            [
                "us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:1.1.0",
                "-jar",
                "/app/ingestion-bundled.jar",
                "--runner=DirectRunner",
                "--projectId=default",
                "--spannerInstanceId=default",
                "--spannerDatabaseId=test-db",
                "--emulatorHost=spanner:15000",
                "--gcsEndpoint=http://gcs:9099/storage/v1",
                f"--importList={json.dumps(import_list)}",
            ]
        )
        run_command(cmd, env=compose_env)
    finally:
        # Clean up temporary credentials file
        if dummy_creds_path.exists():
            dummy_creds_path.unlink()


@pytest.fixture(scope="module")
def docker_stack(services_image, helper_image, keep_containers):
    """Fixture to spin up and tear down emulated service container stack."""
    check_docker_environment()
    root_dir = Path(__file__).resolve().parent
    compose_file = root_dir / "docker-compose.test.yml"

    compose_env = os.environ.copy()
    if services_image:
        compose_env["SERVICES_IMAGE"] = services_image
    if helper_image:
        compose_env["HELPER_IMAGE"] = helper_image

    dc_api_key = os.environ.get("DC_API_KEY")
    if not dc_api_key:
        print(
            ">>> DC_API_KEY environment variable not set. Attempting to fetch 'dc-api-key' secret from datcom-ci project using local gcloud...",
            flush=True,
        )
        try:
            proc = subprocess.run(
                [  # noqa: S607
                    "gcloud",
                    "secrets",
                    "versions",
                    "access",
                    "latest",
                    "--secret",
                    "dc-api-key",
                    "--project",
                    "datcom-ci",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            dc_api_key = proc.stdout.strip()
            print(
                ">>> Successfully fetched 'dc-api-key' from Secret Manager.",
                flush=True,
            )
        except Exception as e:  # noqa: BLE001
            print(
                f">>> WARNING: Failed to fetch 'dc-api-key' from GCP Secret Manager: {e}",
                flush=True,
            )
            print(
                ">>> The pipeline will use 'dummy-key' which might cause 401 errors during ingestion.",
                flush=True,
            )

    if dc_api_key:
        compose_env["DC_API_KEY"] = dc_api_key

    # Pass configuration port mappings into compose runner
    compose_env["WEBSITE_PORT"] = str(WEBSITE_PORT)
    compose_env["HELPER_PORT"] = str(HELPER_PORT)
    compose_env["SPANNER_GRPC_PORT"] = str(SPANNER_GRPC_PORT)
    compose_env["SPANNER_REST_PORT"] = str(SPANNER_REST_PORT)
    compose_env["MOCK_NL_PORT"] = str(MOCK_NL_PORT)

    # 1. Clear any stale containers first
    print("\n>>> Clearing any stale docker containers...", flush=True)
    run_command(
        ["docker", "compose", "-f", str(compose_file), "down", "-v"],
        check=False,
        env=compose_env,
    )

    try:
        try:
            # 2. Boot Spanner and GCS emulators
            print(
                ">>> Starting local Spanner and GCS emulator containers...", flush=True
            )
            run_command(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(compose_file),
                    "up",
                    "-d",
                    "spanner",
                    "gcs",
                ],
                env=compose_env,
            )

            # 3. Wait for Spanner Emulator ready
            wait_for_spanner()

            # Wait for GCS Emulator ready
            wait_for_service(
                "http://localhost:9099/storage/v1/b?project=test-project",
                "GCS emulator",
            )
            seed_gcs_emulator()

            # 4. Create database instance
            create_spanner_db()

            # 5. Boot Ingestion Helper
            print(">>> Starting Ingestion Helper container...", flush=True)
            run_command(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(compose_file),
                    "up",
                    "-d",
                    "ingestion-helper",
                ],
                env=compose_env,
            )

            # 6. Wait for Ingestion Helper responsive
            wait_for_service(
                f"http://localhost:{HELPER_PORT}/docs",
                "Ingestion Helper",
                method="GET",
                expected_statuses=(200,),
                timeout_secs=120,
            )

            # 7. Run DDL schema and seeding
            print(">>> Running database schema DDL migrations...", flush=True)
            init_res = call_helper("initialize_database")
            if init_res.get("status") not in ("success", "OK", "SUCCESS"):
                raise RuntimeError(f"Database DDL migrations failed: {init_res}")

            print(">>> Seeding database ontology variables...", flush=True)
            seed_res = call_helper("seed_database")
            if seed_res.get("status") not in ("success", "OK", "SUCCESS"):
                raise RuntimeError(f"Database seeding failed: {seed_res}")

            # Run local ingestion processor container (simulates local Dataflow Beam run)
            print(
                ">>> Running local Apache Beam data ingestion processor...", flush=True
            )
            run_command(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(compose_file),
                    "run",
                    "--rm",
                    "datacommons-data-processor",
                ],
                env=compose_env,
            )

            # Load the generated GCS JSON-LD files directly into Spanner using the Java Beam template
            run_spanner_loader(compose_env)

            # 8. Boot Website container

            print(">>> Starting serving Website container...", flush=True)
            run_command(
                ["docker", "compose", "-f", str(compose_file), "up", "-d", "website"],
                env=compose_env,
            )

            # 9. Wait for Website ready
            wait_for_service(
                f"http://localhost:{WEBSITE_PORT}",
                "Website",
                timeout_secs=120,
            )

            print(
                ">>> Staged container stack is healthy and fully running.", flush=True
            )
            yield
        except Exception as e:
            print(f"\n>>> Error during docker stack startup: {e}", flush=True)
            print(">>> Dumping docker container logs for debugging:", flush=True)
            try:
                subprocess.run(  # noqa: S603
                    ["docker", "compose", "-f", str(compose_file), "logs"],  # noqa: S607
                    env=compose_env,
                    check=False,
                )
            except Exception as log_ex:  # noqa: BLE001
                print(f"Failed to dump docker logs: {log_ex}", file=sys.stderr)
            raise e
    finally:
        if not keep_containers:
            print("\n>>> Tearing down container stack...", flush=True)
            run_command(
                ["docker", "compose", "-f", str(compose_file), "down", "-v"],
                check=False,
                env=compose_env,
            )
            print(">>> Containers stopped and volumes cleared", flush=True)
        else:
            print("\n>>> Keeping containers running for debugging", flush=True)


# =============================================================================
# Pytest Assertions / Test Cases
# =============================================================================


def assert_golden(
    actual_data: any, golden_filename: str, *, generate_golden: bool
) -> None:

    golden_dir = Path(__file__).resolve().parent / "golden"
    golden_path = golden_dir / golden_filename

    # Format JSON strings deterministically (keys sorted)
    actual_json = json.dumps(actual_data, indent=2, sort_keys=True)

    if generate_golden:
        golden_dir.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(actual_json, encoding="utf-8")
        print(f"\n>>> Generated golden file: {golden_path}", flush=True)
        return

    if not golden_path.exists():
        raise FileNotFoundError(
            f"Golden file not found at {golden_path}. "
            "Run test with --generate-golden flag to create it."
        )

    expected_json = golden_path.read_text(encoding="utf-8")

    if expected_json != actual_json:
        diff = difflib.unified_diff(
            expected_json.splitlines(keepends=True),
            actual_json.splitlines(keepends=True),
            fromfile=f"want: {golden_filename}",
            tofile="got",
        )
        diff_str = "".join(diff)
        raise AssertionError(f"Golden mismatch for {golden_filename}:\n{diff_str}")


@pytest.mark.usefixtures("docker_stack")
def test_spanner_node_seeding(generate_golden):
    """Verify that Spanner contains the base seeded triples and Node rows."""

    # Configure client to query the local Spanner emulator
    os.environ["SPANNER_EMULATOR_HOST"] = f"localhost:{SPANNER_GRPC_PORT}"

    client = spanner.Client(project=PROJECT_ID)
    instance = client.instance(INSTANCE_ID)
    database = instance.database(DATABASE_ID)

    with database.snapshot() as snapshot:
        results = snapshot.execute_sql(
            "SELECT subject_id, name, types, value FROM Node ORDER BY subject_id"
        )
        nodes = [
            {
                "subject_id": row[0],
                "name": row[1],
                "types": list(row[2]) if row[2] else [],
                "value": row[3],
            }
            for row in results
        ]

    assert_golden(nodes, "spanner_nodes.json", generate_golden=generate_golden)


@pytest.mark.usefixtures("docker_stack")
def test_website_serving_home():
    """Verify that the Website root endpoint is up and returns HTTP 200."""
    resp = requests.get(f"http://localhost:{WEBSITE_PORT}", timeout=10)
    assert resp.status_code == 200, "Website home failed to respond with HTTP 200."


@pytest.mark.usefixtures("docker_stack")
def test_spanner_observations(generate_golden):
    """Verify that Spanner contains the correct observations from the seeded OECD wages dataset."""

    os.environ["SPANNER_EMULATOR_HOST"] = f"localhost:{SPANNER_GRPC_PORT}"

    client = spanner.Client(project=PROJECT_ID)
    instance = client.instance(INSTANCE_ID)
    database = instance.database(DATABASE_ID)

    with database.snapshot() as snapshot:
        results = snapshot.execute_sql(
            "SELECT entity1, variable_measured, facet_id, value, date FROM Observation ORDER BY entity1, variable_measured, date"
        )
        obs = [
            {
                "entity1": row[0],
                "variable_measured": row[1],
                "facet_id": row[2],
                "value": row[3],
                "date": row[4],
            }
            for row in results
        ]

    assert_golden(obs, "spanner_observations.json", generate_golden=generate_golden)


@pytest.mark.usefixtures("docker_stack")
def test_website_semantic_nl_query(generate_golden):

    os.environ["SPANNER_EMULATOR_HOST"] = f"localhost:{SPANNER_GRPC_PORT}"

    # Fetch a statistical variable name dynamically from Spanner Node table to stay schema agnostic
    client = spanner.Client(project=PROJECT_ID)
    instance = client.instance(INSTANCE_ID)
    database = instance.database(DATABASE_ID)

    stat_var_name = "Average annual wage"
    with database.snapshot() as snapshot:
        results = snapshot.execute_sql(
            "SELECT name FROM Node WHERE 'StatisticalVariable' IN UNNEST(types) LIMIT 1"
        )
        for row in results:
            if row[0]:
                stat_var_name = row[0]
                break

    print(
        f"\n>>> Running semantic NL query for: '{stat_var_name} in United States of America'",
        flush=True,
    )
    query_str = urllib.parse.quote(f"{stat_var_name} in United States of America")

    url = f"http://localhost:{WEBSITE_PORT}/api/explore/detect-and-fulfill"
    # CAVEAT / WORKAROUND:
    # Cloud Spanner Emulator does not support vector indexes or ANN search queries
    # (APPROX_COSINE_DISTANCE), failing query compilation with validation errors.
    # We bypass it for local integration tests by disabling Spanner vector search.
    # IMPORTANT: Real GCP-based integration tests must cover this active vector search path.
    resp = requests.post(
        f"{url}?q={query_str}&disable_feature=use_v2_resolve_for_nl_search_vars",
        json={"contextHistory": []},
        timeout=120,
    )
    assert resp.status_code == 200, (
        f"NL Query API returned code {resp.status_code}. Response: {resp.text}"
    )

    response_body = resp.json()

    # Strip dynamic debug field if it exists
    response_body.pop("debug", None)

    assert_golden(response_body, "nl_query_usa.json", generate_golden=generate_golden)


# =============================================================================
# Direct CLI Runner Entrypoint
# =============================================================================

if __name__ == "__main__":
    # If executed directly, run pytest on this file
    sys.exit(pytest.main(sys.argv + [__file__]))
