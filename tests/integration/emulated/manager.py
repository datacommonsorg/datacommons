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

"""Local Emulated Stack Manager for hermetic integration testing.

High-level coordinator connecting container lifecycle (stack.py) and dataset
ingestion (loader.py) to provide a local, credentials-free DCPTarget to pytest.
"""

from tests.integration.core.config_schema import TestManifest
from tests.integration.core.target import ArtifactConfig, DCPTarget
from tests.integration.emulated.loader import EmulatedDataLoader
from tests.integration.emulated.stack import DockerComposeStack


class EmulatedStackManager:
    """Coordinates local Docker Compose infrastructure and dataset seeding."""

    def __init__(
        self,
        website_port: int = 8082,
        helper_port: int = 8081,
        spanner_grpc_port: int = 9010,
        spanner_rest_port: int = 9020,
        gcs_port: int = 9099,
        mock_nl_port: int = 6060,
    ):
        self.stack = DockerComposeStack(
            website_port=website_port,
            helper_port=helper_port,
            spanner_grpc_port=spanner_grpc_port,
            spanner_rest_port=spanner_rest_port,
            gcs_port=gcs_port,
            mock_nl_port=mock_nl_port,
        )
        self.loader = EmulatedDataLoader(
            helper_port=self.stack.helper_port,
            gcs_port=self.stack.gcs_port,
        )

    def get_target(self, artifacts: ArtifactConfig | None = None) -> DCPTarget:
        """Returns resolved DCPTarget context for the local emulated stack."""
        return self.stack.get_target(artifacts)

    def start(
        self,
        manifest: TestManifest | None = None,
        artifacts: ArtifactConfig | None = None,
        reuse_data: bool = False,
    ) -> DCPTarget:
        """Starts all Docker services, seeds schema & data, and returns the target."""
        if reuse_data and self.stack.is_healthy():
            print("\n" + "=" * 80)
            print("⚡ [Emulated Stack] Reusing already running local containers (--reuse-data enabled)!")
            print("=" * 80 + "\n")
            return self.stack.get_target(artifacts)

        print("\n" + "=" * 80)
        print("🚀 [Emulated Stack] Bootstrapping hermetic local Docker Compose environment...")
        print("=" * 80)

        env = self.stack.get_compose_env(artifacts)

        # 1. Start core infrastructure (Spanner emulator, Fake GCS, Ingestion Helper)
        self.stack.start_infrastructure(env)

        # 2. Initialize schema DDL and seed ontology nodes
        self.loader.initialize_schema_and_base_nodes()

        # 3. Process and ingest test manifest dataset if specified
        if manifest:
            self.loader.ingest_manifest_dataset(manifest, env)

        # 4. Start serving tier (Mock NL and Website)
        self.stack.start_serving(env)

        print("✔ [Emulated Stack] All local services are ready!\n")
        return self.stack.get_target(artifacts)

    def stop(self) -> None:
        """Stops and tears down all local Docker Compose containers."""
        self.stack.stop()
