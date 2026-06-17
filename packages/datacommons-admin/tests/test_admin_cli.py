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
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from datacommons_admin.admin_cli import admin


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@patch("datacommons_admin.admin_cli._get_github_templates")
def test_init_success_with_options(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\nnamespace  = "$$NAMESPACE$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "test-project",
                "--namespace",
                "test-ns",
                "--dc-api-key",
                "test-key",
                "--no-tf-remote-state",
            ],
        )
        assert result.exit_code == 0
        assert "Downloaded and populated Terraform templates." in result.output

        target_dir = Path.cwd() / "test-ns"
        assert target_dir.exists()
        assert (target_dir / "main.tf").exists()
        assert (target_dir / "terraform.tfvars").exists()
        assert (target_dir / "README.md").exists()
        assert not (target_dir / "backend.tf").exists()

        tfvars_content = (target_dir / "terraform.tfvars").read_text()
        assert 'project_id = "test-project"' in tfvars_content
        assert 'namespace  = "test-ns"' in tfvars_content
        assert 'dc_api_key = "test-key"' in tfvars_content


@patch("datacommons_admin.admin_cli._get_github_templates")
def test_init_success_with_prompts(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\nnamespace  = "$$NAMESPACE$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            ["init", "--no-tf-remote-state"],
            input="prompt-project\nprompt-ns\nprompt-key\n",
        )
        assert result.exit_code == 0
        target_dir = Path.cwd() / "prompt-ns"
        assert target_dir.exists()

        tfvars_content = (target_dir / "terraform.tfvars").read_text()
        assert 'project_id = "prompt-project"' in tfvars_content
        assert 'namespace  = "prompt-ns"' in tfvars_content


@patch("datacommons_admin.admin_cli._get_github_templates")
def test_init_existing_folder_force(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\nnamespace  = "$$NAMESPACE$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        existing_dir = Path.cwd() / "existing-ns"
        existing_dir.mkdir()
        (existing_dir / "main.tf").write_text("old content")

        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "test-project",
                "--namespace",
                "existing-ns",
                "--force",
                "--no-tf-remote-state",
            ],
            input="test-key\n",
        )
        assert result.exit_code == 0
        assert "Downloaded and populated Terraform templates." in result.output

        main_tf = existing_dir / "main.tf"
        assert "old content" not in main_tf.read_text()
        assert 'module "stack"' in main_tf.read_text()


@patch("datacommons_admin.admin_cli._get_github_templates")
@patch("datacommons_admin.admin_cli._configure_remote_state")
def test_init_remote_state(
    mock_configure: patch, mock_get_templates: patch, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\nnamespace  = "$$NAMESPACE$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    mock_configure.return_value = "mock-bucket-name"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "remote-project",
                "--namespace",
                "remote-ns",
                "--dc-api-key",
                "remote-key",
            ],
        )
        assert result.exit_code == 0
        mock_configure.assert_called_once_with("remote-project", "remote-ns", "", "US")

        target_dir = Path.cwd() / "remote-ns"
        assert (target_dir / "backend.tf").exists()
        backend_content = (target_dir / "backend.tf").read_text()
        assert 'bucket = "mock-bucket-name"' in backend_content


@patch("datacommons_admin.tf_utils.shutil.which")
def test_init_db_no_terraform(mock_which: patch, runner: CliRunner) -> None:
    mock_which.return_value = None
    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code != 0
    assert "Terraform CLI not found" in result.output


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
def test_init_db_terraform_error(
    mock_run: patch, mock_which: patch, runner: CliRunner
) -> None:
    mock_which.return_value = "terraform"
    import subprocess

    mock_run.side_effect = subprocess.CalledProcessError(
        1, ["terraform"], stderr="not a terraform dir"
    )
    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code != 0
    assert "Failed to run 'terraform output'" in result.output


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_init_db_success(
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    from unittest.mock import MagicMock

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success", "message": "DB Initialized"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code == 0
    assert "Successfully initialized Spanner database" in result.output
    assert "Successfully seeded Spanner database" in result.output


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_init_db_init_only(
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    from unittest.mock import MagicMock

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success", "message": "DB Initialized"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    result = runner.invoke(admin, ["init-db", "--init-only"])
    assert result.exit_code == 0
    assert "Successfully initialized Spanner database" in result.output
    assert "Seeding Spanner database" not in result.output


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_seed_db_success(
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    from unittest.mock import MagicMock

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success", "message": "DB Seeded"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    result = runner.invoke(admin, ["seed-db"])
    assert result.exit_code == 0
    assert "Successfully seeded Spanner database" in result.output


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_ingest_start_success(
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    from unittest.mock import MagicMock

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_prep_job_name": {"value": "projects/mock-proj/locations/us-central1/jobs/mock-job"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "project_id": {"value": "mock-proj"}, "region": {"value": "us-central1"}, "ingestion_workflow_name": {"value": "mock-workflow"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "operationName": "projects/mock-proj/locations/us-central1/operations/op-123"
    }
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    result = runner.invoke(admin, ["ingest", "start"])
    assert result.exit_code == 0
    assert "Successfully started ingestion job!" in result.output
    assert (
        "Operation details: projects/mock-proj/locations/us-central1/operations/op-123"
        in result.output
    )
    assert "Operation ID: op-123" in result.output
    assert (
        "Job Console Link: https://console.cloud.google.com/run/jobs/details/us-central1/mock-job/executions?project=mock-proj"
        in result.output
    )


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_ingest_show_config_success(
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    from unittest.mock import MagicMock

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_prep_job_name": {"value": "mock-job"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "project_id": {"value": "mock-proj"}, "region": {"value": "us-central1"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "config": [
            {"name": "GCS_BUCKET", "value": "my-test-bucket"},
            {"name": "API_KEY", "valueSource": "secret-api-key"},
        ]
    }
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    result = runner.invoke(admin, ["ingest", "show-config"])
    assert result.exit_code == 0
    assert "GCS_BUCKET: my-test-bucket" in result.output
    assert "API_KEY: [SECRET: secret-api-key]" in result.output


@patch("datacommons_admin.admin_cli._get_github_templates")
def test_init_uses_default_ref_v_prefixed(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\nnamespace  = "$$NAMESPACE$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    from datacommons_admin import __version__

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "ref-project",
                "--namespace",
                "ref-ns",
                "--dc-api-key",
                "ref-key",
                "--no-tf-remote-state",
            ],
        )
        assert result.exit_code == 0
        mock_get_templates.assert_called_once_with(f"v{__version__}")


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_ingest_start_with_imports_success(
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    from unittest.mock import MagicMock

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_prep_job_name": {"value": "projects/mock-proj/locations/us-central1/jobs/mock-job"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "project_id": {"value": "mock-proj"}, "region": {"value": "us-central1"}, "ingestion_workflow_name": {"value": "mock-workflow"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "operationName": "projects/mock-proj/locations/us-central1/operations/op-123"
    }
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    result = runner.invoke(admin, ["ingest", "start", "--imports", "oecd,doubleup"])
    assert result.exit_code == 0
    assert "Successfully started ingestion job!" in result.output
    mock_session_inst.post.assert_called_once_with(
        "https://mock-helper/ingestion/start",
        json={
            "imports": "oecd,doubleup",
        },
        timeout=300,
    )
