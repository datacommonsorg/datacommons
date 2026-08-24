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

"""Docker Compose Stack Manager for the local emulated test environment.

Handles container lifecycle, dynamic port allocation, and readiness probing.
"""

import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import requests
from google.cloud import spanner

from tests.integration.core.target import ArtifactConfig, DCPTarget

EMULATED_DIR = Path(__file__).resolve().parent
COMPOSE_FILE = EMULATED_DIR / "docker-compose.yml"


def _get_free_port(default_port: int) -> int:
    """Binds to default port or finds an available open socket port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", default_port))
            return default_port
        except OSError:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                s2.bind(("", 0))
                return s2.getsockname()[1]


class DockerComposeStack:
    """Manages Docker Compose container lifecycle for the local emulated environment."""

    def __init__(
        self,
        website_port: int = 8082,
        helper_port: int = 8081,
        spanner_grpc_port: int = 9010,
        spanner_rest_port: int = 9020,
        gcs_port: int = 9099,
        mock_nl_port: int = 6060,
    ):
        self.website_port = int(os.environ.get("WEBSITE_PORT", website_port))
        self.helper_port = int(os.environ.get("HELPER_PORT", helper_port))
        self.spanner_grpc_port = int(os.environ.get("SPANNER_GRPC_PORT", spanner_grpc_port))
        self.spanner_rest_port = int(os.environ.get("SPANNER_REST_PORT", spanner_rest_port))
        self.gcs_port = int(os.environ.get("GCS_PORT", gcs_port))
        self.mock_nl_port = int(os.environ.get("MOCK_NL_PORT", mock_nl_port))
        self._is_running = False

    def is_healthy(self) -> bool:
        """Checks if local website and spanner containers are already running and healthy."""
        try:
            resp = requests.get(f"http://localhost:{self.website_port}/healthz", timeout=1)
            return resp.status_code == 200
        except Exception:
            return False

    def get_compose_env(self, artifacts: ArtifactConfig | None = None) -> dict[str, str]:
        """Constructs environment variables for Docker Compose."""
        env = os.environ.copy()
        env["WEBSITE_PORT"] = str(self.website_port)
        env["HELPER_PORT"] = str(self.helper_port)
        env["SPANNER_GRPC_PORT"] = str(self.spanner_grpc_port)
        env["SPANNER_REST_PORT"] = str(self.spanner_rest_port)
        env["MOCK_NL_PORT"] = str(self.mock_nl_port)
        env["SPANNER_PROJECT_ID"] = "default"
        env["SPANNER_INSTANCE_ID"] = "default"
        env["SPANNER_DATABASE_ID"] = "test-db"

        if artifacts:
            if artifacts.services_image:
                env["SERVICES_IMAGE"] = artifacts.services_image
            if artifacts.helper_image:
                env["HELPER_IMAGE"] = artifacts.helper_image
            if artifacts.preprocessing_image:
                env["PROCESSOR_IMAGE"] = artifacts.preprocessing_image

        return env

    def get_target(self, artifacts: ArtifactConfig | None = None) -> DCPTarget:
        """Returns the resolved DCPTarget descriptor for this local stack."""
        return DCPTarget(
            project_id="default",
            instance_name="local",
            workspace_dir=str(EMULATED_DIR),
            serving_url=f"http://localhost:{self.website_port}",
            helper_url=f"http://localhost:{self.helper_port}",
            spanner_instance="default",
            spanner_database="test-db",
            workflow_name="local-workflow",
            workflow_sa_email="local-sa@default.iam.gserviceaccount.com",
            gcs_bucket="test-bucket",
            artifacts=artifacts or ArtifactConfig(),
        )

    def start_infrastructure(self, env: dict[str, str]) -> None:
        """Starts Spanner, Fake GCS, and Ingestion Helper containers."""
        self._check_docker()
        self._cleanup_stale(env)

        # 1. Start Spanner and GCS
        print(">>> Starting Spanner and GCS emulator containers...")
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "spanner", "gcs"],
            cwd=str(EMULATED_DIR),
            env=env,
            check=True,
        )
        self._wait_for_spanner()
        self._create_spanner_database()

        # 2. Start Ingestion Helper
        print(">>> Starting Ingestion Helper container...")
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "ingestion-helper"],
            cwd=str(EMULATED_DIR),
            env=env,
            check=True,
        )
        self._wait_for_service(
            f"http://localhost:{self.helper_port}/docs",
            "Ingestion Helper",
            timeout_secs=60,
        )

    def start_serving(self, env: dict[str, str]) -> None:
        """Starts Mock NL and Website serving containers."""
        print(">>> Starting Mock NL and Website services...")
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "mock-nl-server", "website"],
            cwd=str(EMULATED_DIR),
            env=env,
            check=True,
        )
        self._wait_for_service(
            f"http://localhost:{self.website_port}/healthz",
            "Website",
            timeout_secs=60,
        )
        self._is_running = True

    def stop(self, env: dict[str, str] | None = None) -> None:
        """Tears down all running Docker Compose containers."""
        if not self._is_running:
            return
        print("\n>>> [Emulated Stack] Tearing down local containers...")
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
            cwd=str(EMULATED_DIR),
            env=env or os.environ.copy(),
            capture_output=True,
            check=False,
        )
        self._is_running = False
        print("✔ [Emulated Stack] Teardown complete.\n")

    def _check_docker(self) -> None:
        res = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise RuntimeError("❌ Docker daemon is not reachable. Please start Docker Desktop.")

    def _cleanup_stale(self, env: dict[str, str]) -> None:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
            cwd=str(EMULATED_DIR),
            env=env,
            capture_output=True,
            check=False,
        )
        subprocess.run(
            [
                "docker", "rm", "-f",
                "itest-website", "itest-mock-nl-server", "itest-spanner",
                "itest-gcs", "itest-ingestion-helper", "itest-datacommons-data-processor",
            ],
            capture_output=True,
            check=False,
        )
        subprocess.run(["docker", "network", "rm", "itest-net"], capture_output=True, check=False)

    def _wait_for_spanner(self, timeout_secs: int = 45) -> None:
        start = time.time()
        while time.time() - start < timeout_secs:
            try:
                with socket.create_connection(("127.0.0.1", self.spanner_grpc_port), timeout=1):
                    return
            except (TimeoutError, ConnectionRefusedError, OSError):
                time.sleep(0.5)
        raise RuntimeError(f"Spanner emulator failed to start on port {self.spanner_grpc_port}")

    def _create_spanner_database(self) -> None:
        os.environ["SPANNER_EMULATOR_HOST"] = f"127.0.0.1:{self.spanner_grpc_port}"
        client = spanner.Client(project="default")
        instance = client.instance(
            "default",
            configuration_name="projects/default/instanceConfigs/emulator-config",
            node_count=1,
        )
        if not instance.exists():
            op = instance.create()
            op.result(timeout=30)
        database = instance.database("test-db")
        if not database.exists():
            op = database.create()
            op.result(timeout=30)

    def _wait_for_service(
        self,
        url: str,
        name: str,
        expected_statuses: tuple[int, ...] = (200,),
        timeout_secs: int = 60,
    ) -> None:
        print(f"Waiting for {name} to be ready at {url}...")
        start = time.time()
        while time.time() - start < timeout_secs:
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code in expected_statuses:
                    print(f"  ✔ {name} is ready!")
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(0.5)
        raise RuntimeError(f"{name} failed to become ready at {url} within {timeout_secs}s.")
