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

"""Unified local emulated environment manager for hermetic integration tests.

Manages Docker Compose services (Spanner emulator, Fake GCS, Ingestion Helper,
Website, and Mock NL), database schema initialization, and dataset loading.
"""

import contextlib
import json
import subprocess
import time
from pathlib import Path

import requests

from tests.integration.core.config_schema import TestManifest

REPO_ROOT = Path(__file__).resolve().parents[3]
EMULATED_DIR = Path(__file__).resolve().parent
COMPOSE_FILE = EMULATED_DIR / "docker-compose.yml"


class EmulatedEnvironment:
    """Manages local Docker Compose services and database provisioning for tests."""

    def __init__(
        self,
        serving_url: str = "http://localhost:8082",
        helper_url: str = "http://localhost:8081",
        gcs_url: str = "http://localhost:9099",
    ):
        self.serving_url = serving_url
        self.helper_url = helper_url
        self.gcs_url = gcs_url
        self._is_running = False

    def is_healthy(self) -> bool:
        """Checks if the Website and Spanner stack are already up and serving."""
        try:
            resp = requests.get(f"{self.serving_url}/healthz", timeout=1)
            return resp.status_code == 200
        except Exception:
            return False

    def start(
        self, manifest: TestManifest | None = None, reuse_data: bool = False
    ) -> None:
        """Boots required Docker containers, runs migrations, and seeds test data."""
        if reuse_data and self.is_healthy():
            print("\n" + "=" * 80)
            print(
                "⚡ [Emulated Stack] Reusing running containers (--reuse-data enabled)!"
            )
            print("=" * 80 + "\n")
            return

        print("\n" + "=" * 80)
        print(
            "🚀 [Emulated Stack] Bootstrapping hermetic local Docker Compose environment..."
        )
        print("=" * 80)

        self._cleanup_stale()

        # 1. Start core storage and ingestion helper
        print(">>> Starting Spanner emulator, Fake GCS, and Ingestion Helper...")
        self._compose_up("spanner", "gcs", "ingestion-helper")
        self._wait_for_spanner_ready(timeout_secs=30)
        self._wait_for_ready(
            f"{self.helper_url}/docs", "Ingestion Helper", timeout_secs=60
        )

        # 2. Initialize database schema DDL and base ontology
        self._initialize_database()

        # 3. Ingest test dataset if specified
        if manifest and manifest.stages.ingestion and manifest.ingestion.dataset_dirs:
            self._ingest_dataset(manifest)

        # 4. Start serving tier (Website & Mixer)
        print(">>> Starting Website and Mixer services...")
        self._compose_up("website")
        self._wait_for_ready(f"{self.serving_url}/healthz", "Website", timeout_secs=60)
        self._wait_for_mixer_ready(timeout_secs=60)
        self._is_running = True
        print("✔ [Emulated Stack] All local services are ready!\n")

    def stop(self) -> None:
        """Tears down all Docker Compose containers and volumes."""
        if not self._is_running and not self.is_healthy():
            return
        print("\n>>> [Emulated Stack] Tearing down local containers...")
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
            cwd=str(EMULATED_DIR),
            capture_output=True,
            check=False,
        )
        self._is_running = False
        print("✔ [Emulated Stack] Teardown complete.\n")

    def _compose_up(self, *services: str) -> None:
        cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", *services]
        subprocess.run(cmd, cwd=str(EMULATED_DIR), check=True)

    def _initialize_database(self) -> None:
        print(">>> Ensuring test-db database exists in Spanner emulator...")
        with contextlib.suppress(Exception):
            from google.auth.credentials import AnonymousCredentials
            from google.cloud import spanner

            client = spanner.Client(
                project="default", credentials=AnonymousCredentials()
            )
            instance = client.instance("default")
            db = instance.database("test-db")
            if not db.exists():
                db.create().result(timeout=30)

        print(">>> Initializing database schema DDL via Ingestion Helper (streaming logs)...")
        def _do_initialize():
            resp = requests.post(
                f"{self.helper_url}/database/initialize",
                json={"actionType": "initialize_database"},
                timeout=120,
            )
            resp.raise_for_status()

        self._stream_container_logs_during("itest-ingestion-helper", _do_initialize)

        print(">>> Seeding database base ontology variables...")
        def _do_seed():
            resp = requests.post(
                f"{self.helper_url}/database/seed",
                json={"actionType": "seed_database"},
                timeout=60,
            )
            resp.raise_for_status()

        self._stream_container_logs_during("itest-ingestion-helper", _do_seed)

    def _ingest_dataset(self, manifest: TestManifest) -> None:
        print(">>> Seeding GCS emulator and running ingestion pipeline...")
        # 1. Ensure test bucket exists in GCS emulator
        with contextlib.suppress(Exception):
            requests.post(
                f"{self.gcs_url}/storage/v1/b?project=test-project",
                json={"name": "test-bucket"},
                timeout=5,
            )

        # 2. Upload dataset files to GCS emulator
        import_names = []
        for d in manifest.ingestion.dataset_dirs:
            import_dir = REPO_ROOT / d if not Path(d).is_absolute() else Path(d)
            if not import_dir.exists():
                continue
            import_name = import_dir.name
            import_names.append(import_name)
            for file_path in import_dir.glob("*"):
                if file_path.is_file() and not file_path.name.startswith("."):
                    with open(file_path, "rb") as f:
                        data = f.read()
                    resp = requests.post(
                        f"{self.gcs_url}/upload/storage/v1/b/test-bucket/o?uploadType=media&name=ingestion/input/{import_name}/{file_path.name}",
                        data=data,
                        timeout=10,
                    )
                    resp.raise_for_status()

        # 3. Run Apache Beam data processor
        imports_arg = ",".join(import_names) if import_names else "wages"
        proc_cmd = [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "run",
            "--rm",
            "datacommons-data-processor",
            "--input_dir=gs://test-bucket/ingestion/input",
            "--output_dir=gs://test-bucket/output",
            "--mode=dcpbridge",
            f"--imports={imports_arg}",
        ]
        subprocess.run(proc_cmd, cwd=str(EMULATED_DIR), check=True)

        # 4. Run Java Spanner loader (GraphIngestionPipeline on DirectRunner)
        gcs_resp = requests.get(
            f"{self.gcs_url}/storage/v1/b/test-bucket/o", timeout=10
        ).json()
        jsonld_blobs = [
            item["name"]
            for item in gcs_resp.get("items", [])
            if item["name"].endswith(".jsonld")
        ]
        top_dirs = {
            "/".join(name.split("/")[:3])
            if len(name.split("/")) >= 3
            else "/".join(name.split("/")[:-1])
            for name in jsonld_blobs
        }
        if not top_dirs:
            return

        import_list = [
            {
                "importName": d.split("/")[-1].split("_")[0],
                "graphPath": f"gs://test-bucket/{d}/*/*.jsonld",
            }
            for d in top_dirs
        ]

        loader_cmd = [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "java",
            "--network",
            "itest-net",
            "-e",
            "SPANNER_EMULATOR_HOST=spanner:15000",
            "-e",
            "STORAGE_EMULATOR_HOST=http://gcs:9099",
            "-e",
            "GOOGLE_CLOUD_SPANNER_MULTIPLEXED_SESSIONS=TRUE",
            "-e",
            "GOOGLE_CLOUD_SPANNER_MULTIPLEXED_SESSIONS_FOR_RW=TRUE",
            "-e",
            "NO_GCE_CHECK=true",
            "us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:latest",
            "-cp",
            "/template/*",
            "org.datacommons.ingestion.pipeline.GraphIngestionPipeline",
            "--runner=DirectRunner",
            "--projectId=default",
            "--spannerInstanceId=default",
            "--spannerDatabaseId=test-db",
            "--emulatorHost=spanner:15000",
            "--gcsEndpoint=http://gcs:9099/storage/v1",
            f"--importList={json.dumps(import_list)}",
        ]
        subprocess.run(loader_cmd, check=True)

    def _wait_for_ready(self, url: str, name: str, timeout_secs: int = 60) -> None:
        start = time.time()
        while time.time() - start < timeout_secs:
            try:
                if requests.get(url, timeout=2).status_code in (200, 404):
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(0.5)
        raise RuntimeError(
            f"❌ {name} failed to become ready at {url} within {timeout_secs}s."
        )

    def _wait_for_mixer_ready(self, timeout_secs: int = 60) -> None:
        start = time.time()
        while time.time() - start < timeout_secs:
            try:
                resp = requests.post(
                    f"{self.serving_url}/core/api/v2/node",
                    json={"nodes": ["average_annual_wage"], "property": "->name"},
                    headers={"X-Use-Multi-Entity-Schema": "true"},
                    timeout=2,
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    if "average_annual_wage" in data and data["average_annual_wage"]:
                        return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError(
            f"❌ Mixer failed to populate Spanner graph cache within {timeout_secs}s."
        )

    def _wait_for_spanner_ready(self, timeout_secs: int = 30) -> None:
        start = time.time()
        while time.time() - start < timeout_secs:
            try:
                from google.auth.credentials import AnonymousCredentials
                from google.cloud import spanner

                client = spanner.Client(
                    project="default", credentials=AnonymousCredentials()
                )
                list(client.list_instances())
                return
            except Exception:
                time.sleep(1)
        raise RuntimeError("❌ Spanner emulator failed to become ready in time.")

    def _stream_container_logs_during(self, container_name: str, target_fn):
        """Streams container logs to terminal in real time while target_fn executes."""
        import threading

        stop_event = threading.Event()

        def _stream():
            try:
                proc = subprocess.Popen(
                    ["docker", "logs", "-f", "--tail", "0", container_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                while not stop_event.is_set():
                    line = proc.stdout.readline() if proc.stdout else ""
                    if line:
                        print(f"[{container_name}] {line.rstrip()}", flush=True)
                    elif proc.poll() is not None:
                        break
                proc.terminate()
            except Exception:
                pass

        thread = threading.Thread(target=_stream, daemon=True)
        thread.start()
        try:
            return target_fn()
        finally:
            stop_event.set()
            time.sleep(0.3)

    def _cleanup_stale(self) -> None:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
            cwd=str(EMULATED_DIR),
            capture_output=True,
            check=False,
        )
        subprocess.run(
            [
                "docker",
                "rm",
                "-f",
                "itest-spanner",
                "itest-gcs",
                "itest-ingestion-helper",
                "itest-website",
                "itest-datacommons-data-processor",
            ],
            capture_output=True,
            check=False,
        )
