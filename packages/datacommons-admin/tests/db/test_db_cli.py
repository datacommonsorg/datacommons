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

import subprocess
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner
from datacommons_admin.admin_cli import admin


@patch("datacommons_admin.shared_utils.tf_utils.shutil.which")
def test_init_db_no_terraform(mock_which, runner: CliRunner) -> None:
    mock_which.return_value = None
    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code != 0
    assert "Terraform CLI not found" in result.output


@patch("datacommons_admin.shared_utils.tf_utils.shutil.which")
@patch("datacommons_admin.shared_utils.tf_utils.subprocess.run")
def test_init_db_terraform_error(mock_run, mock_which, runner: CliRunner) -> None:
    mock_which.return_value = "terraform"
    mock_run.side_effect = subprocess.CalledProcessError(
        1, ["terraform"], stderr="not a terraform dir"
    )
    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code != 0
    assert "Failed to run 'terraform output'" in result.output


@patch("datacommons_admin.db.db_cli._run_migrations")
@patch("datacommons_admin.shared_utils.tf_utils.shutil.which")
@patch("datacommons_admin.shared_utils.tf_utils.subprocess.run")
@patch("datacommons_admin.db.clients.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.db.clients.ingestion_helper_client.google.auth.default")
def test_init_db_success(
    mock_auth_default,
    mock_session,
    mock_run,
    mock_which,
    mock_run_migrations,
    runner: CliRunner,
    mock_tf_output_spanner: str,
) -> None:
    mock_which.return_value = "terraform"
    mock_proc = MagicMock()
    mock_proc.stdout = mock_tf_output_spanner
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


@patch("datacommons_admin.db.db_cli._run_migrations")
@patch("datacommons_admin.shared_utils.tf_utils.shutil.which")
@patch("datacommons_admin.shared_utils.tf_utils.subprocess.run")
@patch("datacommons_admin.db.clients.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.db.clients.ingestion_helper_client.google.auth.default")
def test_init_db_success_no_details(
    mock_auth_default,
    mock_session,
    mock_run,
    mock_which,
    mock_run_migrations,
    runner: CliRunner,
    mock_tf_output_spanner: str,
) -> None:
    mock_which.return_value = "terraform"
    mock_proc = MagicMock()
    mock_proc.stdout = mock_tf_output_spanner
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


@patch("datacommons_admin.db.db_cli._run_migrations")
@patch("datacommons_admin.shared_utils.tf_utils.shutil.which")
@patch("datacommons_admin.shared_utils.tf_utils.subprocess.run")
@patch("datacommons_admin.db.clients.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.db.clients.ingestion_helper_client.google.auth.default")
def test_init_db_init_only(
    mock_auth_default,
    mock_session,
    mock_run,
    mock_which,
    mock_run_migrations,
    runner: CliRunner,
    mock_tf_output_spanner: str,
) -> None:
    mock_which.return_value = "terraform"
    mock_proc = MagicMock()
    mock_proc.stdout = mock_tf_output_spanner
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


@patch("datacommons_admin.db.db_cli._run_migrations")
@patch("datacommons_admin.shared_utils.tf_utils.shutil.which")
@patch("datacommons_admin.shared_utils.tf_utils.subprocess.run")
@patch("datacommons_admin.db.clients.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.db.clients.ingestion_helper_client.google.auth.default")
def test_init_db_migration_failure_halts_before_seed(
    mock_auth_default,
    mock_session,
    mock_run,
    mock_which,
    mock_run_migrations,
    runner: CliRunner,
    mock_tf_output_spanner: str,
) -> None:
    mock_which.return_value = "terraform"
    mock_proc = MagicMock()
    mock_proc.stdout = mock_tf_output_spanner
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


@patch("datacommons_admin.shared_utils.tf_utils.shutil.which")
@patch("datacommons_admin.shared_utils.tf_utils.subprocess.run")
@patch("datacommons_admin.db.clients.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.db.clients.ingestion_helper_client.google.auth.default")
def test_seed_db_success(
    mock_auth_default,
    mock_session,
    mock_run,
    mock_which,
    runner: CliRunner,
    mock_tf_output_spanner: str,
) -> None:
    mock_which.return_value = "terraform"
    mock_proc = MagicMock()
    mock_proc.stdout = mock_tf_output_spanner
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
