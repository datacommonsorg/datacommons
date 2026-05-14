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

from click.testing import CliRunner
import pytest

from datacommons_admin.admin_cli import admin, init


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_init_success_with_options(runner: CliRunner, tmp_path: Path) -> None:
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
            ],
            input="N\n",  # Do not configure remote state
        )
        assert result.exit_code == 0
        assert "Initialized Terraform scaffold" in result.output

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


def test_init_success_with_prompts(runner: CliRunner, tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            ["init"],
            input="prompt-project\nprompt-ns\nprompt-key\nN\n",
        )
        assert result.exit_code == 0
        target_dir = Path.cwd() / "prompt-ns"
        assert target_dir.exists()

        tfvars_content = (target_dir / "terraform.tfvars").read_text()
        assert 'project_id = "prompt-project"' in tfvars_content
        assert 'namespace  = "prompt-ns"' in tfvars_content


def test_init_existing_folder_force(runner: CliRunner, tmp_path: Path) -> None:
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
            ],
            input="test-key\nN\n",
        )
        assert result.exit_code == 0
        assert "Initialized Terraform scaffold" in result.output

        main_tf = existing_dir / "main.tf"
        assert "old content" not in main_tf.read_text()
        assert 'module "datacommons_dcp"' in main_tf.read_text()


@patch("datacommons_admin.admin_cli._configure_remote_state")
def test_init_remote_state(
    mock_configure: patch, runner: CliRunner, tmp_path: Path
) -> None:
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
            input="Y\n",  # Yes to remote state
        )
        assert result.exit_code == 0
        mock_configure.assert_called_once_with("remote-project", "remote-ns")

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
    mock_proc.stdout = '{"dcp_ingestion_helper_uri": {"value": "https://mock-helper"}, "dcp_orchestrator_service_account_email": {"value": "mock-orch-sa@mock.com"}, "dcp_spanner_instance_id": {"value": "mock-instance"}, "dcp_spanner_database_id": {"value": "mock-db"}}'
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
    mock_proc.stdout = '{"dcp_ingestion_helper_uri": {"value": "https://mock-helper"}, "dcp_orchestrator_service_account_email": {"value": "mock-orch-sa@mock.com"}, "dcp_spanner_instance_id": {"value": "mock-instance"}, "dcp_spanner_database_id": {"value": "mock-db"}}'
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
    mock_proc.stdout = '{"dcp_ingestion_helper_uri": {"value": "https://mock-helper"}, "dcp_orchestrator_service_account_email": {"value": "mock-orch-sa@mock.com"}, "dcp_spanner_instance_id": {"value": "mock-instance"}, "dcp_spanner_database_id": {"value": "mock-db"}}'
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
