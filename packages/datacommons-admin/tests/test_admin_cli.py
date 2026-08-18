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

import click
import pytest
from click.testing import CliRunner
from datacommons_admin.admin_cli import admin
from datacommons_db.clients.spanner_client import ExecutionStatus
from datacommons_db.migrations.migration_runner import MigrationResult


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
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "test-project",
                "--instance-name",
                "test-instance",
                "--dc-api-key",
                "test-key",
                "--no-tf-remote-state",
            ],
        )
        assert result.exit_code == 0
        assert "Downloaded and populated Terraform templates." in result.output

        target_dir = Path.cwd() / "test-instance"
        assert target_dir.exists()
        assert (target_dir / "main.tf").exists()
        assert (target_dir / "terraform.tfvars").exists()
        assert (target_dir / "README.md").exists()
        assert not (target_dir / "backend.tf").exists()

        tfvars_content = (target_dir / "terraform.tfvars").read_text()
        assert 'project_id = "test-project"' in tfvars_content
        assert 'instance_name  = "test-instance"' in tfvars_content
        assert 'dc_api_key = "test-key"' in tfvars_content


@patch("datacommons_admin.admin_cli._get_github_templates")
def test_init_success_with_deprecated_namespace_flag(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "test-project",
                "--namespace",
                "legacy-namespace",
                "--dc-api-key",
                "test-key",
                "--no-tf-remote-state",
            ],
        )
        assert result.exit_code == 0
        target_dir = Path.cwd() / "legacy-namespace"
        assert target_dir.exists()
        tfvars_content = (target_dir / "terraform.tfvars").read_text()
        assert 'instance_name  = "legacy-namespace"' in tfvars_content


@patch("datacommons_admin.admin_cli._get_github_templates")
def test_init_success_with_prompts(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            ["init", "--no-tf-remote-state"],
            input="prompt-project\nprompt-instance\nprompt-key\n",
        )
        assert result.exit_code == 0
        target_dir = Path.cwd() / "prompt-instance"
        assert target_dir.exists()

        tfvars_content = (target_dir / "terraform.tfvars").read_text()
        assert 'project_id = "prompt-project"' in tfvars_content
        assert 'instance_name  = "prompt-instance"' in tfvars_content


@patch("datacommons_admin.admin_cli._get_github_templates")
def test_init_existing_folder_force(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        existing_dir = Path.cwd() / "existing-dcp"
        existing_dir.mkdir()
        (existing_dir / "main.tf").write_text("old content")

        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "test-project",
                "--instance-name",
                "existing-dcp",
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
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    mock_configure.return_value = "mock-bucket-name"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "remote-project",
                "--instance-name",
                "remote-instance",
                "--dc-api-key",
                "remote-key",
            ],
        )
        assert result.exit_code == 0
        mock_configure.assert_called_once_with(
            "remote-project", "remote-instance", "", "US"
        )

        target_dir = Path.cwd() / "remote-instance"
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


@patch("datacommons_admin.admin_cli._run_migrations")
@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_init_db_success(
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    mock_run_migrations: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    from unittest.mock import MagicMock

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
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
    assert "Details: DB Initialized" in result.output
    assert "Successfully seeded Spanner database" in result.output
    mock_run_migrations.assert_called_once()


@patch("datacommons_admin.admin_cli._run_migrations")
@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_init_db_success_no_details(
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    mock_run_migrations: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    from unittest.mock import MagicMock

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success", "message": None}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code == 0
    assert "Successfully initialized Spanner database" in result.output
    assert "Details:" not in result.output
    assert "Successfully seeded Spanner database" in result.output
    mock_run_migrations.assert_called_once()


@patch("datacommons_admin.admin_cli._run_migrations")
@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_init_db_init_only(
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    mock_run_migrations: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    from unittest.mock import MagicMock

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
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
    mock_run_migrations.assert_called_once()


@patch("datacommons_admin.admin_cli._run_migrations")
@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_init_db_migration_failure_halts_before_seed(
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    mock_run_migrations: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    from unittest.mock import MagicMock

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success", "message": "DB Initialized"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    mock_run_migrations.side_effect = click.ClickException("Migration failed")

    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code != 0
    assert "Successfully initialized Spanner database" in result.output
    assert "Migration failed" in result.output
    # Seeding should NOT be called if migrations fail
    assert "Seeding Spanner database" not in result.output
    assert "Successfully seeded Spanner database" not in result.output


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
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
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
@patch("datacommons_admin.ingestion_job_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_job_client.google.auth.default")
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
    mock_proc.stdout = '{"ingestion_prep_job_name": {"value": "projects/mock-proj/locations/us-central1/jobs/mock-job"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "project_id": {"value": "mock-proj"}, "region": {"value": "us-central1"}, "ingestion_workflow_name": {"value": "mock-workflow"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()

    # Mock GET for get_config
    mock_get_resp = MagicMock()
    mock_get_resp.ok = True
    mock_get_resp.json.return_value = {
        "template": {
            "template": {
                "containers": [
                    {
                        "env": [
                            {"name": "TEMP_LOCATION", "value": "gs://mock-bucket/temp"},
                            {
                                "name": "GCP_SPANNER_INSTANCE_ID",
                                "value": "mock-instance",
                            },
                            {"name": "GCP_SPANNER_DATABASE_NAME", "value": "mock-db"},
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
    mock_session.return_value = mock_session_inst

    result = runner.invoke(admin, ["ingest", "start", "--imports", "mock-import"])
    assert result.exit_code == 0
    assert "Successfully started ingestion workflow!" in result.output
    assert "Execution ID: exec-123" in result.output
    assert (
        "Execution console link: https://console.cloud.google.com/workflows/workflow/us-central1/mock-workflow/execution/exec-123/summary?project=mock-proj"
        in result.output
    )


def test_ingest_start_fails_without_imports_flag(runner: CliRunner) -> None:
    result = runner.invoke(admin, ["ingest", "start"])
    assert result.exit_code != 0
    assert "Missing option '--imports'" in result.output


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_job_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_job_client.google.auth.default")
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
    mock_proc.stdout = '{"ingestion_prep_job_name": {"value": "mock-job"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "project_id": {"value": "mock-proj"}, "region": {"value": "us-central1"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "template": {
            "template": {
                "containers": [
                    {
                        "env": [
                            {"name": "GCS_BUCKET", "value": "my-test-bucket"},
                            {"name": "API_KEY", "valueSource": "secret-api-key"},
                        ]
                    }
                ]
            }
        }
    }
    mock_session_inst.get.return_value = mock_resp
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
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    from datacommons_admin import __version__

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "ref-project",
                "--instance-name",
                "ref-instance",
                "--dc-api-key",
                "ref-key",
                "--no-tf-remote-state",
            ],
        )
        assert result.exit_code == 0
        mock_get_templates.assert_called_once_with(f"v{__version__}")


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_job_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_job_client.google.auth.default")
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
    mock_proc.stdout = '{"ingestion_prep_job_name": {"value": "projects/mock-proj/locations/us-central1/jobs/mock-job"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "project_id": {"value": "mock-proj"}, "region": {"value": "us-central1"}, "ingestion_workflow_name": {"value": "mock-workflow"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()

    # Mock GET for get_config
    mock_get_resp = MagicMock()
    mock_get_resp.ok = True
    mock_get_resp.json.return_value = {
        "template": {
            "template": {
                "containers": [
                    {
                        "env": [
                            {"name": "TEMP_LOCATION", "value": "gs://mock-bucket/temp"},
                            {
                                "name": "GCP_SPANNER_INSTANCE_ID",
                                "value": "mock-instance",
                            },
                            {"name": "GCP_SPANNER_DATABASE_NAME", "value": "mock-db"},
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
    mock_session.return_value = mock_session_inst

    result = runner.invoke(admin, ["ingest", "start", "--imports", "oecd,doubleup"])
    assert result.exit_code == 0
    assert "Successfully started ingestion workflow!" in result.output

    import json

    expected_arg = {
        "tempLocation": "gs://mock-bucket/temp",
        "spannerInstanceId": "mock-instance",
        "spannerDatabaseId": "mock-db",
        "region": "us-central1",
        "imports": ["oecd", "doubleup"],
    }

    # Verify the API was called with the correct argument
    called_args = mock_session_inst.post.call_args[1]
    assert called_args["timeout"] == 300
    called_payload = called_args["json"]
    assert "argument" in called_payload
    assert json.loads(called_payload["argument"]) == expected_arg


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
@patch("datacommons_admin.admin_cli.SpannerClient")
@patch("datacommons_admin.admin_cli.MigrationRunner")
def test_migrate_db_no_pending(
    mock_runner_cls: patch,
    mock_spanner_cls: patch,
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    mock_spanner_cls.return_value = MagicMock()

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_session.return_value = mock_session_inst

    mock_runner_inst = MagicMock()
    mock_runner_inst.get_pending_migrations.return_value = []
    mock_runner_cls.return_value = mock_runner_inst

    result = runner.invoke(admin, ["migrate-db"])
    assert result.exit_code == 0
    assert "Database schema is already up-to-date" in result.output
    # Lock should not be acquired when there are no pending migrations
    mock_session_inst.post.assert_not_called()


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
@patch("datacommons_admin.admin_cli.SpannerClient")
@patch("datacommons_admin.admin_cli.MigrationRunner")
def test_migrate_db_with_pending_success(
    mock_runner_cls: patch,
    mock_spanner_cls: patch,
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    mock_spanner_cls.return_value = MagicMock()

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    mock_migration = MagicMock()
    mock_migration.creation_timestamp = "20260817000000"
    mock_migration.description = "Bootstrap migration"

    mock_runner_inst = MagicMock()
    mock_runner_inst.get_pending_migrations.return_value = [mock_migration]
    mock_runner_inst.run_migrations.return_value = [
        MigrationResult(
            status=ExecutionStatus.SUCCESS,
            creation_timestamp="20260817000000",
            description="Bootstrap migration",
        )
    ]
    mock_runner_cls.return_value = mock_runner_inst

    result = runner.invoke(admin, ["migrate-db"], input="y\n")
    assert result.exit_code == 0
    assert "Found 1 pending schema migration" in result.output
    assert (
        "Warning: Schema migrations will modify your Spanner database schema"
        in result.output
    )
    assert "Applied migration 20260817000000: Bootstrap migration" in result.output
    assert "Successfully applied all schema migrations!" in result.output

    # Check lock acquired then released
    assert mock_session_inst.post.call_count == 2
    mock_session_inst.post.assert_any_call(
        "https://mock-helper/database/lock/acquire",
        json={"workflowId": "schema-migration", "timeout": 300},
        timeout=300,
    )
    mock_session_inst.post.assert_any_call(
        "https://mock-helper/database/lock/release",
        json={"workflowId": "schema-migration"},
        timeout=300,
    )


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
@patch("datacommons_admin.admin_cli.SpannerClient")
@patch("datacommons_admin.admin_cli.MigrationRunner")
def test_migrate_db_with_yes_flag(
    mock_runner_cls: patch,
    mock_spanner_cls: patch,
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    mock_spanner_cls.return_value = MagicMock()

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    mock_migration = MagicMock()
    mock_migration.creation_timestamp = "20260817000000"
    mock_migration.description = "Bootstrap migration"

    mock_runner_inst = MagicMock()
    mock_runner_inst.get_pending_migrations.return_value = [mock_migration]
    mock_runner_inst.run_migrations.return_value = [
        MigrationResult(
            status=ExecutionStatus.SUCCESS,
            creation_timestamp="20260817000000",
            description="Bootstrap migration",
        )
    ]
    mock_runner_cls.return_value = mock_runner_inst

    result = runner.invoke(admin, ["migrate-db", "-y"])
    assert result.exit_code == 0
    assert "Found 1 pending schema migration" in result.output
    assert "Applied migration 20260817000000: Bootstrap migration" in result.output
    assert "Successfully applied all schema migrations!" in result.output
    mock_runner_inst.run_migrations.assert_called_once()


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
@patch("datacommons_admin.admin_cli.SpannerClient")
@patch("datacommons_admin.admin_cli.MigrationRunner")
def test_migrate_db_user_cancels(
    mock_runner_cls: patch,
    mock_spanner_cls: patch,
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    mock_spanner_cls.return_value = MagicMock()

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_session.return_value = mock_session_inst

    mock_migration = MagicMock()
    mock_migration.creation_timestamp = "20260817000000"
    mock_migration.description = "Bootstrap migration"

    mock_runner_inst = MagicMock()
    mock_runner_inst.get_pending_migrations.return_value = [mock_migration]
    mock_runner_cls.return_value = mock_runner_inst

    result = runner.invoke(admin, ["migrate-db"], input="n\n")
    assert result.exit_code == 0
    assert "Found 1 pending schema migration" in result.output
    assert (
        "Warning: Schema migrations will modify your Spanner database schema"
        in result.output
    )
    assert "Migration cancelled." in result.output
    # No lock or migrations should be run
    mock_session_inst.post.assert_not_called()
    mock_runner_inst.run_migrations.assert_not_called()


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
@patch("datacommons_admin.admin_cli.SpannerClient")
@patch("datacommons_admin.admin_cli.MigrationRunner")
def test_migrate_db_default_no_cancels(
    mock_runner_cls: patch,
    mock_spanner_cls: patch,
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    mock_spanner_cls.return_value = MagicMock()

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_session.return_value = mock_session_inst

    mock_migration = MagicMock()
    mock_migration.creation_timestamp = "20260817000000"
    mock_migration.description = "Bootstrap migration"

    mock_runner_inst = MagicMock()
    mock_runner_inst.get_pending_migrations.return_value = [mock_migration]
    mock_runner_cls.return_value = mock_runner_inst

    # Pressing Enter without typing 'y' should default to No and cancel
    result = runner.invoke(admin, ["migrate-db"], input="\n")
    assert result.exit_code == 0
    assert "Found 1 pending schema migration" in result.output
    assert (
        "Warning: Schema migrations will modify your Spanner database schema"
        in result.output
    )
    assert "Migration cancelled." in result.output
    mock_session_inst.post.assert_not_called()
    mock_runner_inst.run_migrations.assert_not_called()


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
@patch("datacommons_admin.admin_cli.SpannerClient")
@patch("datacommons_admin.admin_cli.MigrationRunner")
def test_migrate_db_failure_releases_lock(
    mock_runner_cls: patch,
    mock_spanner_cls: patch,
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    mock_spanner_cls.return_value = MagicMock()

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    mock_migration = MagicMock()
    mock_migration.creation_timestamp = "20260817000000"
    mock_migration.description = "Bootstrap migration"

    mock_runner_inst = MagicMock()
    mock_runner_inst.get_pending_migrations.return_value = [mock_migration]
    mock_runner_inst.run_migrations.side_effect = RuntimeError("DDL operation failed")
    mock_runner_cls.return_value = mock_runner_inst

    result = runner.invoke(admin, ["migrate-db"], input="y\n")
    assert result.exit_code != 0
    assert "Failed to apply schema migrations: DDL operation failed" in result.output

    # Ensure release_lock was still called in finally block
    mock_session_inst.post.assert_any_call(
        "https://mock-helper/database/lock/release",
        json={"workflowId": "schema-migration"},
        timeout=300,
    )


@patch("datacommons_admin.tf_utils.shutil.which")
@patch("datacommons_admin.tf_utils.subprocess.run")
@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
@patch("datacommons_admin.admin_cli.SpannerClient")
@patch("datacommons_admin.admin_cli.MigrationRunner")
def test_migrate_db_lock_busy_error(
    mock_runner_cls: patch,
    mock_spanner_cls: patch,
    mock_auth_default: patch,
    mock_session: patch,
    mock_run: patch,
    mock_which: patch,
    runner: CliRunner,
) -> None:
    mock_which.return_value = "terraform"
    mock_spanner_cls.return_value = MagicMock()

    mock_proc = MagicMock()
    mock_proc.stdout = '{"ingestion_service_url": {"value": "https://mock-helper"}, "ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, "spanner_instance_id": {"value": "mock-instance"}, "spanner_database_id": {"value": "mock-db"}, "project_id": {"value": "mock-proj"}}'
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 503
    mock_resp.json.return_value = {"detail": "Lock busy"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    mock_migration = MagicMock()
    mock_migration.creation_timestamp = "20260817000000"
    mock_migration.description = "Bootstrap migration"

    mock_runner_inst = MagicMock()
    mock_runner_inst.get_pending_migrations.return_value = [mock_migration]
    mock_runner_cls.return_value = mock_runner_inst

    result = runner.invoke(admin, ["migrate-db"], input="y\n")
    assert result.exit_code != 0
    assert "Ingestion Helper returned HTTP 503" in result.output
    assert (
        "Please wait for active ingestions to finish before running migrations"
        in result.output
    )
