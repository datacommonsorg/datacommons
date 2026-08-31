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

from pathlib import Path

import pytest

from tests.integration.core.cli_runner import DatacommonsCLI
from tests.integration.core.config_schema import (
    ExpectedEdge,
    ExpectedNode,
    TestManifest,
)
from tests.integration.core.spanner_client import SpannerClient
from tests.integration.core.target import DCPTarget


@pytest.mark.cloud_only
class TestCLIIngestion:
    """Validates Data Commons CLI ingestion commands against target workspace."""

    def test_01_cli_ingest_show_config(
        self, dcp_cli: DatacommonsCLI, dcp_target: DCPTarget
    ):
        """Validates that 'datacommons admin ingest show-config' outputs matching live workspace configuration."""
        res = dcp_cli.run(["admin", "ingest", "show-config"])
        assert res.exit_code == 0, f"CLI ingest show-config failed: {res.output}"
        assert "Current ingestion job configuration:" in res.output

        expected = [
            f"PROJECT_ID: {dcp_target.project_id}",
            f"GCP_SPANNER_INSTANCE_ID: {dcp_target.spanner_instance}",
            f"GCP_SPANNER_DATABASE_NAME: {dcp_target.spanner_database}",
            f"GCS_BUCKET: {dcp_target.gcs_bucket}",
        ]
        for token in expected:
            if not token.endswith(": "):
                assert token in res.output, (
                    f"Missing '{token}' in CLI show-config output"
                )

    def test_02_cli_init_db(
        self,
        request,
        dcp_cli: DatacommonsCLI,
        test_manifest: TestManifest,
    ):
        """Validates that 'datacommons admin init-db' initializes and seeds the Spanner database."""
        if request.config.getoption("--reuse-data"):
            pytest.skip(
                "Skipped Spanner database initialization because --reuse-data was specified."
            )

        if not test_manifest.stages.ingestion:
            pytest.skip("Ingestion stage disabled in test manifest.")

        res = dcp_cli.run(["admin", "init-db"])
        assert res.exit_code == 0, f"CLI init-db failed: {res.output}"
        assert "Successfully initialized Spanner database!" in res.output

    def test_03_cli_ingest_start(
        self,
        request,
        seeded_testbed,
        dcp_cli: DatacommonsCLI,
        dcp_target: DCPTarget,
        spanner_client: SpannerClient,
        test_manifest: TestManifest,
    ):
        """Validates that 'datacommons admin ingest start' triggers and completes Cloud Workflows."""
        if request.config.getoption("--reuse-data"):
            pytest.skip("Skipped full workflow run because --reuse-data was specified.")

        if not test_manifest.stages.ingestion:
            pytest.skip("Ingestion stage disabled in test manifest.")

        import_dirs = test_manifest.ingestion.dataset_dirs
        if not import_dirs:
            pytest.skip(
                "No dataset_dirs defined in test manifest ingestion configuration."
            )

        import_names = [Path(d).name for d in import_dirs]
        imports_arg = ",".join(import_names)

        # 1. Run the CLI ingestion start command
        res = dcp_cli.run(["admin", "ingest", "start", "--imports", imports_arg])
        assert res.exit_code == 0, f"Failed to start ingestion via CLI: {res.output}"
        assert "Successfully started ingestion workflow!" in res.output

        # 2. Extract Execution ID
        exec_id = res.extract_execution_id()
        assert exec_id is not None, (
            f"Could not extract Execution ID from CLI output: {res.output}"
        )

        # 3. Wait for Cloud Workflows and Dataflow completion
        wf_timeout = request.config.getoption("--workflow-timeout") or 2400
        completed = dcp_cli.wait_for_workflow(
            execution_id=exec_id,
            workflow_name=dcp_target.workflow_name,
            project_id=dcp_target.project_id,
            timeout_seconds=wf_timeout,
        )
        assert completed, f"Cloud Workflow execution '{exec_id}' failed or timed out."

        # 4. Verify Spanner IngestionHistory record if table exists
        history = spanner_client.get_ingestion_history(exec_id)
        if history is not None:
            assert history.get("Status") == "SUCCESS", (
                f"IngestionHistory status is '{history.get('Status')}', expected 'SUCCESS' for workflow '{exec_id}'"
            )


class TestSpannerGraph:
    """Validates declared knowledge graph nodes and edges in Cloud Spanner Node and Edge tables."""

    def test_04_spanner_node_exists(
        self,
        seeded_testbed,
        spanner_client: SpannerClient,
        expected_node_spec: ExpectedNode | None,
    ):
        """Verifies specific node exists in Spanner Node table with expected types."""
        if not expected_node_spec:
            pytest.skip("No nodes defined in manifest or ingestion stage disabled.")

        node = spanner_client.get_node(expected_node_spec.subject_id)
        assert node is not None, (
            f"Expected node '{expected_node_spec.subject_id}' not found in Spanner Node table"
        )

        if expected_node_spec.expected_types:
            node_types = node.get("types", []) or []
            for t in expected_node_spec.expected_types:
                assert t in node_types or any(t in str(x) for x in node_types), (
                    f"Node '{expected_node_spec.subject_id}' missing expected type '{t}'. Actual types: {node_types}"
                )

    def test_05_spanner_edge_exists(
        self,
        seeded_testbed,
        spanner_client: SpannerClient,
        expected_edge_spec: ExpectedEdge | None,
    ):
        """Verifies specific (subject, predicate, object) edge exists in Spanner Edge table."""
        if not expected_edge_spec:
            pytest.skip("No edges defined in manifest or ingestion stage disabled.")

        sql = (
            "SELECT subject_id, predicate, object_id FROM Edge "
            "WHERE subject_id = @sid AND predicate = @pred AND object_id = @obj LIMIT 1"
        )
        params = {
            "sid": expected_edge_spec.subject_id,
            "pred": expected_edge_spec.predicate,
            "obj": expected_edge_spec.object_id,
        }
        rows = spanner_client.query(sql, params=params)
        assert len(rows) > 0, (
            f"Expected edge ({expected_edge_spec.subject_id} -> {expected_edge_spec.predicate} -> {expected_edge_spec.object_id}) "
            "not found in Spanner Edge table"
        )
