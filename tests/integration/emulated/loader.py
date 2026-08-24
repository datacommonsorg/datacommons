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

"""Dataset and Schema Ingestion Loader for the local emulated test environment.

Executes schema DDL migrations, base ontology seeding, Apache Beam data processing,
and Java Dataflow Spanner loading into the local Spanner emulator.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import requests

from tests.integration.core.config_schema import TestManifest

REPO_ROOT = Path(__file__).resolve().parents[3]
EMULATED_DIR = Path(__file__).resolve().parent
COMPOSE_FILE = EMULATED_DIR / "docker-compose.yml"


class EmulatedDataLoader:
    """Manages database initialization, dataset seeding, and Beam/Spanner ingestion pipelines."""

    def __init__(self, helper_port: int = 8081, gcs_port: int = 9099):
        self.helper_port = helper_port
        self.gcs_port = gcs_port

    def initialize_schema_and_base_nodes(self) -> None:
        """Triggers schema DDL initialization and ontology seeding via Ingestion Helper."""
        print(">>> Running database schema DDL migrations via Ingestion Helper...")
        self._call_helper("database/initialize", {"actionType": "initialize_database"})
        print(">>> Seeding database ontology variables...")
        self._call_helper("database/seed", {"actionType": "seed_database"})

    def ingest_manifest_dataset(self, manifest: TestManifest, env: dict[str, str]) -> None:
        """Uploads manifest test data to GCS emulator and runs Beam + Spanner loader pipelines."""
        if not (manifest.stages.ingestion and manifest.ingestion.dataset_dirs):
            return

        import_names = self._seed_gcs_data(manifest)
        self._run_data_processor(import_names, env)
        self._run_spanner_loader(env)

    def _call_helper(self, path: str, payload: dict) -> dict:
        url = f"http://localhost:{self.helper_port}/{path}"
        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                return {"status": "success", "message": resp.text}
        except Exception as e:
            raise RuntimeError(f"Ingestion helper call to {path} failed: {e}") from e

    def _seed_gcs_data(self, manifest: TestManifest) -> list[str]:
        print(">>> Seeding GCS emulator with dataset input files...")
        # 1. Create fake GCS bucket under test-project
        try:
            requests.post(
                f"http://localhost:{self.gcs_port}/storage/v1/b?project=test-project",
                json={"name": "test-bucket"},
                timeout=5,
            )
        except Exception:
            pass

        # 2. Upload dummy custom_catalog.yaml
        dummy_catalog = "version: '1'\nmodels: {}\nindexes: {}\n"
        try:
            requests.post(
                f"http://localhost:{self.gcs_port}/upload/storage/v1/b/test-bucket/o?uploadType=media&name=output/datacommons/nl/embeddings/custom_catalog.yaml",
                data=dummy_catalog,
                headers={"Content-Type": "application/x-yaml"},
                timeout=5,
            )
        except Exception:
            pass

        # 3. Upload dataset files to GCS emulator
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
                    requests.post(
                        f"http://localhost:{self.gcs_port}/upload/storage/v1/b/test-bucket/o?uploadType=media&name=ingestion/input/{import_name}/{file_path.name}",
                        data=data,
                        timeout=10,
                    )
        print(f"  ✔ Dataset files for {import_names} uploaded to GCS emulator.")
        return import_names

    def _run_data_processor(self, import_names: list[str], env: dict[str, str]) -> None:
        print(">>> Running local Apache Beam data processor...")
        imports_arg = ",".join(import_names) if import_names else "wages"
        cmd = [
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
        subprocess.run(cmd, cwd=str(EMULATED_DIR), env=env, check=True)
        print("  ✔ Apache Beam data processor complete.")

    def _run_spanner_loader(self, env: dict[str, str]) -> None:
        print(">>> Running local Java Spanner Loader pipeline...")
        try:
            resp = requests.get(f"http://localhost:{self.gcs_port}/storage/v1/b/test-bucket/o", timeout=10)
            resp.raise_for_status()
            items = [item["name"] for item in resp.json().get("items", [])]
        except Exception as e:
            raise RuntimeError(f"Failed to query GCS emulator: {e}") from e

        jsonld_blobs = [name for name in items if name.endswith(".jsonld")]
        top_dirs = set()
        for name in jsonld_blobs:
            parts = name.split("/")
            if len(parts) >= 3:
                top_dirs.add("/".join(parts[:3]))
            elif len(parts) >= 2:
                top_dirs.add("/".join(parts[:-1]))

        if not top_dirs:
            print("  [Warning] No JSON-LD files found in GCS emulator for Spanner loader.")
            return

        import_list = []
        for d in top_dirs:
            top_folder = d.split("/")[-1]
            import_name = top_folder.split("_")[0]
            import_list.append({"importName": import_name, "graphPath": f"gs://test-bucket/{d}/*/*.jsonld"})

        cmd = [
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
            f"--gcsEndpoint=http://gcs:{self.gcs_port}/storage/v1",
            f"--importList={json.dumps(import_list)}",
        ]
        subprocess.run(cmd, env=env, check=True)
        print("  ✔ Local Java Spanner Loader pipeline complete.")
