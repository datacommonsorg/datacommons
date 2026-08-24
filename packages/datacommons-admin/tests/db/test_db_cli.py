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
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner
from datacommons_admin.admin_cli import admin


def test_init_db_no_terraform(runner: CliRunner) -> None:
    with patch(
        "datacommons_admin.core.utils.tf_utils.shutil.which", return_value=None
    ):
        result = runner.invoke(admin, ["init-db"])
        assert result.exit_code != 0
        assert "Terraform CLI not found" in result.output


def test_init_db_terraform_error(runner: CliRunner) -> None:
    with (
        patch(
            "datacommons_admin.core.utils.tf_utils.shutil.which",
            return_value="terraform",
        ),
        patch(
            "datacommons_admin.core.utils.tf_utils.subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, ["terraform"], stderr="not a terraform dir"
            ),
        ),
    ):
        result = runner.invoke(admin, ["init-db"])
        assert result.exit_code != 0
        assert "Failed to run 'terraform output'" in result.output


@pytest.mark.usefixtures("mock_terraform_spanner", "mock_helper_session")
def test_init_db_success(
    mock_run_migrations,
    runner: CliRunner,
) -> None:
    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code == 0
    assert "Successfully initialized Spanner database" in result.output
    assert "Details: DB Initialized" in result.output
    assert "Successfully seeded Spanner database" in result.output
    mock_run_migrations.assert_called_once()


@pytest.mark.usefixtures("mock_terraform_spanner")
def test_init_db_success_no_details(
    mock_helper_session,
    mock_run_migrations,
    runner: CliRunner,
) -> None:
    mock_helper_session.post.return_value.json.return_value = {
        "status": "success",
        "message": None,
    }
    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code == 0
    assert "Successfully initialized Spanner database" in result.output
    assert "Details:" not in result.output
    assert "Successfully seeded Spanner database" in result.output
    mock_run_migrations.assert_called_once()


@pytest.mark.usefixtures("mock_terraform_spanner", "mock_helper_session")
def test_init_db_init_only(
    mock_run_migrations,
    runner: CliRunner,
) -> None:
    result = runner.invoke(admin, ["init-db", "--init-only"])
    assert result.exit_code == 0
    assert "Successfully initialized Spanner database" in result.output
    assert "Seeding Spanner database" not in result.output
    mock_run_migrations.assert_called_once()


@pytest.mark.usefixtures("mock_terraform_spanner", "mock_helper_session")
def test_init_db_migration_failure_halts_before_seed(
    mock_run_migrations,
    runner: CliRunner,
) -> None:
    mock_run_migrations.side_effect = click.ClickException("Migration failed")

    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code != 0
    assert "Successfully initialized Spanner database" in result.output
    assert "Migration failed" in result.output
    # Seeding should NOT be called if migrations fail
    assert "Seeding Spanner database" not in result.output
    assert "Successfully seeded Spanner database" not in result.output


@pytest.mark.usefixtures("mock_terraform_spanner")
def test_seed_db_success(
    mock_helper_session,
    runner: CliRunner,
) -> None:
    mock_helper_session.post.return_value.json.return_value = {
        "status": "success",
        "message": "DB Seeded",
    }
    result = runner.invoke(admin, ["seed-db"])
    assert result.exit_code == 0
    assert "Successfully seeded Spanner database" in result.output
