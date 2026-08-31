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
import os
import subprocess
import time
from pathlib import Path

import requests
from google.auth.credentials import AnonymousCredentials
from google.cloud import spanner

from datacommons_db.clients.spanner_client import (
    SpannerClient as DCPSpannerClient,
)
from datacommons_db.migrations import MigrationRunner
from tests.integration.core.config_schema import TestManifest

REPO_ROOT = Path(__file__).resolve().parents[3]
EMULATED_DIR = Path(__file__).resolve().parent
COMPOSE_FILE = EMULATED_DIR / "docker-compose.yml"


class EmulatedEnvironment:
    """Manages local Docker Compose services and database provisioning for tests."""

    def __init__(
        self,
        serving_url: str | None = None,
        helper_url: str | None = None,
        gcs_url: str | None = None,
    ):
        self.serving_url = serving_url or os.getenv(
            "DCP_SERVING_URL", "http://localhost:8082"
        )
        self.helper_url = helper_url or os.getenv(
            "DCP_HELPER_URL", "http://localhost:8081"
        )
        self.gcs_url = gcs_url or os.getenv(
            "STORAGE_EMULATOR_HOST", "http://localhost:9099"
        )
        self.spanner_host = os.getenv("SPANNER_EMULATOR_HOST", "localhost:9010")
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

        print("\n" + "=" * 80, flush=True)
        print(
            "🚀 [Emulated Stack] Bootstrapping hermetic local Docker Compose environment...",
            flush=True,
        )
        print("=" * 80, flush=True)

        os.environ["SPANNER_EMULATOR_HOST"] = self.spanner_host
        os.environ["STORAGE_EMULATOR_HOST"] = self.gcs_url

        self._cleanup_stale()

        # 1. Start core storage and ingestion helper
        print(
            ">>> Starting Spanner emulator, Fake GCS, and Ingestion Helper...",
            flush=True,
        )
        self._compose_up("spanner", "gcs", "ingestion-helper")
        self._wait_for_spanner_ready(timeout_secs=60)
        self._wait_for_ready(
            f"{self.helper_url}/docs", "Ingestion Helper", timeout_secs=60
        )

        # 2. Initialize database schema DDL and base ontology
        self._initialize_database()

        # 3. Ingest test dataset if specified
        if manifest and manifest.stages.ingestion and manifest.ingestion.dataset_dirs:
            self._ingest_dataset(manifest)

        # 4. Start serving tier (Website & Mixer)
        print(">>> Starting Website and Mixer services (streaming logs)...", flush=True)
        self._compose_up("website")

        def _do_wait_website():
            self._wait_for_ready(
                f"{self.serving_url}/healthz", "Website", timeout_secs=90
            )

        self._stream_container_logs_during("itest-website", _do_wait_website)
        self._wait_for_mixer_ready(manifest=manifest, timeout_secs=90)
        self._is_running = True
        print("✔ [Emulated Stack] All local services are ready!\n", flush=True)

    def stop(self) -> None:
        """Tears down all Docker Compose containers and volumes."""
        if not self._is_running and not self.is_healthy():
            return
        print("\n>>> [Emulated Stack] Tearing down local containers...", flush=True)
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
            cwd=str(EMULATED_DIR),
            capture_output=True,
            check=False,
        )
        self._is_running = False
        print("✔ [Emulated Stack] Teardown complete.\n", flush=True)

    def _compose_up(self, *services: str) -> None:
        cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", *services]
        subprocess.run(cmd, cwd=str(EMULATED_DIR), check=True)
        hostname = os.getenv("HOSTNAME", "")
        if hostname:
            subprocess.run(
                ["docker", "network", "connect", "itest-net", hostname],
                capture_output=True,
                check=False,
            )

    def _initialize_database(self) -> None:
        # Provisioned in fixture setup so downstream test suites can run in isolation.
        print(">>> Ensuring test-db database exists in Spanner emulator...", flush=True)
        client = spanner.Client(project="default", credentials=AnonymousCredentials())
        instance = client.instance("default")
        db = instance.database("test-db")
        if not db.exists():
            db.create().result(timeout=30)

        print(
            ">>> Initializing database schema DDL via Ingestion Helper (streaming logs)...",
            flush=True,
        )

        def _do_initialize():
            resp = requests.post(
                f"{self.helper_url}/database/initialize",
                json={"actionType": "initialize_database"},
                timeout=120,
            )
            resp.raise_for_status()

        self._stream_container_logs_during("itest-ingestion-helper", _do_initialize)

        print(">>> Applying schema migrations via MigrationRunner...", flush=True)
        dcp_spanner = DCPSpannerClient(
            project_id="default",
            instance_id="default",
            database_id="test-db",
            credentials=AnonymousCredentials(),
        )
        runner = MigrationRunner(dcp_spanner)
        runner.run_migrations()

        print(">>> Seeding database base ontology variables...", flush=True)

        def _do_seed():
            resp = requests.post(
                f"{self.helper_url}/database/seed",
                json={"actionType": "seed_database"},
                timeout=60,
            )
            resp.raise_for_status()

        self._stream_container_logs_during("itest-ingestion-helper", _do_seed)

    def _ingest_dataset(self, manifest: TestManifest) -> None:
        print(">>> Seeding GCS emulator and running ingestion pipeline...", flush=True)
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
        resp = requests.get(f"{self.gcs_url}/storage/v1/b/test-bucket/o", timeout=10)
        resp.raise_for_status()
        gcs_resp = resp.json()
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
            "-e",
            "IS_BASE_DC=false",
            os.getenv(
                "DATAFLOW_IMAGE",
                "us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:latest",
            ),
            "-cp",
            "/template/*",
            "org.datacommons.ingestion.pipeline.GraphIngestionPipeline",
            "--runner=DirectRunner",
            "--projectId=default",
            "--spannerInstanceId=default",
            "--spannerDatabaseId=test-db",
            "--emulatorHost=spanner:15000",
            "--gcsEndpoint=http://gcs:9099/storage/v1",
            "--isBaseDc=false",
            f"--importList={json.dumps(import_list)}",
        ]
        subprocess.run(loader_cmd, check=True)

    def _wait_for_ready(self, url: str, name: str, timeout_secs: int = 90) -> None:
        start = time.time()
        while time.time() - start < timeout_secs:
            try:
                if requests.get(url, timeout=2).status_code in (200, 404):
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(0.5)
        container_logs = ""
        with contextlib.suppress(Exception):
            c_name = f"itest-{name.lower()}"
            proc = subprocess.run(
                ["docker", "logs", "--tail", "100", c_name],
                capture_output=True,
                text=True,
                check=False,
            )
            logs = proc.stdout or proc.stderr or ""
            if logs:
                container_logs = f"\n--- Container {c_name} logs ---\n{logs}"
        raise RuntimeError(
            f"❌ {name} failed to become ready at {url} within {timeout_secs}s.{container_logs}"
        )

    def _wait_for_mixer_ready(
        self, manifest: TestManifest | None = None, timeout_secs: int = 90
    ) -> None:
        """Polls Mixer until Spanner graph cache is loaded and ready to serve.

        NOTE (Temporary): Probing node ensures the in-memory Spanner Property
        Graph cache in Mixer has finished its asynchronous initial warmup cycle before
        the test suites begin assertions. This will be superseded once Mixer exposes
        a dedicated readiness endpoint.
        """
        probe_node = "dc/g/Root"
        if (
            manifest
            and manifest.ingestion
            and manifest.ingestion.spanner_expectations
            and manifest.ingestion.spanner_expectations.expected_nodes
        ):
            probe_node = manifest.ingestion.spanner_expectations.expected_nodes[0].subject_id

        start = time.time()
        while time.time() - start < timeout_secs:
            try:
                resp = requests.post(
                    f"{self.serving_url}/core/api/v2/node",
                    json={"nodes": [probe_node], "property": "->name"},
                    headers={"X-Use-Multi-Entity-Schema": "true"},
                    timeout=2,
                )
                if resp.status_code == 200 and probe_node in resp.json().get("data", {}):
                    return
            except Exception:
                pass
            time.sleep(0.5)
        container_logs = ""
        with contextlib.suppress(Exception):
            proc = subprocess.run(
                ["docker", "logs", "--tail", "100", "itest-website"],
                capture_output=True,
                text=True,
                check=False,
            )
            logs = proc.stdout or proc.stderr or ""
            if logs:
                container_logs = f"\n--- Container itest-website logs ---\n{logs}"
        raise RuntimeError(
            f"❌ Mixer failed to populate Spanner graph cache for 'dc/g/Root' within {timeout_secs}s.{container_logs}"
        )

    def _wait_for_spanner_ready(self, timeout_secs: int = 60) -> None:
        print(
            f">>> Waiting for Spanner emulator to accept connections at {self.spanner_host}...",
            flush=True,
        )
        os.environ["SPANNER_EMULATOR_HOST"] = self.spanner_host
        start = time.time()
        while time.time() - start < timeout_secs:
            try:
                client = spanner.Client(
                    project="default", credentials=AnonymousCredentials()
                )
                list(client.list_instances())
                print("✔ Spanner emulator is ready!", flush=True)
                return
            except Exception:
                time.sleep(1)
        container_logs = ""
        with contextlib.suppress(Exception):
            proc = subprocess.run(
                ["docker", "logs", "--tail", "100", "itest-spanner"],
                capture_output=True,
                text=True,
                check=False,
            )
            logs = proc.stdout or proc.stderr or ""
            if logs:
                container_logs = f"\n--- Container itest-spanner logs ---\n{logs}"
        raise RuntimeError(
            f"❌ Spanner emulator at {self.spanner_host} failed to become ready in time.{container_logs}"
        )

    def _stream_container_logs_during(self, container_name: str, target_fn):
        """Streams container logs to terminal in real time while target_fn executes."""
        import threading

        proc = subprocess.Popen(
            ["docker", "logs", "-f", "--tail", "0", container_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        def _stream():
            try:
                for line in iter(proc.stdout.readline, ""):
                    print(f"[{container_name}] {line.rstrip()}", flush=True)
            except Exception:
                pass

        thread = threading.Thread(target=_stream, daemon=True)
        thread.start()
        try:
            return target_fn()
        finally:
            proc.terminate()
            with contextlib.suppress(Exception):
                proc.wait(timeout=2.0)
            thread.join(timeout=1.0)

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
