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
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def isolated_runner(runner: CliRunner, tmp_path: Path):
    """Provides a CliRunner running inside an isolated temporary filesystem."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        yield runner


@pytest.fixture
def mock_tf_output_spanner() -> str:
    """Returns a mock JSON string representing Terraform outputs for DB commands."""
    return (
        '{"ingestion_service_url": {"value": "https://mock-helper"}, '
        '"ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, '
        '"spanner_instance_id": {"value": "mock-instance"}, '
        '"spanner_database_id": {"value": "mock-db"}, '
        '"project_id": {"value": "mock-proj"}}'
    )


@pytest.fixture
def mock_tf_output_ingest() -> str:
    """Returns a mock JSON string representing Terraform outputs for Ingest commands."""
    return (
        '{"ingestion_prep_job_name": {"value": "projects/mock-proj/locations/us-central1/jobs/mock-job"}, '
        '"ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, '
        '"project_id": {"value": "mock-proj"}, '
        '"region": {"value": "us-central1"}, '
        '"ingestion_workflow_name": {"value": "mock-workflow"}}'
    )


@pytest.fixture
def mock_github_templates():
    """Mocks _get_github_templates returning standard template strings."""
    templates = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with patch(
        "datacommons_admin.init.utils.scaffold_utils._get_github_templates",
        return_value=templates,
    ) as mock_get:
        yield mock_get


@pytest.fixture
def mock_terraform_spanner(mock_tf_output_spanner: str):
    """Mocks Terraform CLI check and terraform output for DB commands."""
    with (
        patch(
            "datacommons_admin.core.utils.tf_utils.shutil.which",
            return_value="terraform",
        ),
        patch("datacommons_admin.core.utils.tf_utils.subprocess.run") as mock_run,
    ):
        mock_proc = MagicMock()
        mock_proc.stdout = mock_tf_output_spanner
        mock_run.return_value = mock_proc
        yield mock_run


@pytest.fixture
def mock_terraform_ingest(mock_tf_output_ingest: str):
    """Mocks Terraform CLI check and terraform output for Ingest commands."""
    with (
        patch(
            "datacommons_admin.core.utils.tf_utils.shutil.which",
            return_value="terraform",
        ),
        patch("datacommons_admin.core.utils.tf_utils.subprocess.run") as mock_run,
    ):
        mock_proc = MagicMock()
        mock_proc.stdout = mock_tf_output_ingest
        mock_run.return_value = mock_proc
        yield mock_run


@pytest.fixture
def mock_helper_session():
    """Mocks AuthorizedSession and google.auth.default for ingestion helper client."""
    with (
        patch(
            "datacommons_admin.core.clients.ingestion_helper_client.google.auth.default"
        ) as mock_auth_default,
        patch(
            "datacommons_admin.core.clients.ingestion_helper_client.AuthorizedSession"
        ) as mock_session_cls,
    ):
        mock_creds = MagicMock()
        mock_auth_default.return_value = (mock_creds, "test-project")

        mock_session_inst = MagicMock()
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "status": "success",
            "message": "DB Initialized",
        }
        mock_session_inst.post.return_value = mock_resp
        mock_session_cls.return_value = mock_session_inst
        yield mock_session_inst


@pytest.fixture
def mock_job_session():
    """Mocks AuthorizedSession and google.auth.default for ingestion job client."""
    with (
        patch(
            "datacommons_admin.core.clients.ingestion_job_client.google.auth.default"
        ) as mock_auth_default,
        patch(
            "datacommons_admin.core.clients.ingestion_job_client.AuthorizedSession"
        ) as mock_session_cls,
    ):
        mock_creds = MagicMock()
        mock_auth_default.return_value = (mock_creds, "test-project")

        mock_session_inst = MagicMock()

        mock_get_resp = MagicMock()
        mock_get_resp.ok = True
        mock_get_resp.json.return_value = {
            "template": {
                "template": {
                    "containers": [
                        {
                            "env": [
                                {
                                    "name": "TEMP_LOCATION",
                                    "value": "gs://mock-bucket/temp",
                                },
                                {
                                    "name": "GCP_SPANNER_INSTANCE_ID",
                                    "value": "mock-instance",
                                },
                                {
                                    "name": "GCP_SPANNER_DATABASE_NAME",
                                    "value": "mock-db",
                                },
                                {"name": "REGION", "value": "us-central1"},
                            ]
                        }
                    ]
                }
            }
        }
        mock_session_inst.get.return_value = mock_get_resp

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "name": "projects/mock-proj/locations/us-central1/workflows/mock-workflow/executions/exec-123"
        }
        mock_session_inst.post.return_value = mock_resp
        mock_session_cls.return_value = mock_session_inst
        yield mock_session_inst


@pytest.fixture
def mock_run_migrations():
    """Mocks _run_migrations for db commands."""
    with patch("datacommons_admin.db.db_cli._run_migrations") as mock_fn:
        yield mock_fn
