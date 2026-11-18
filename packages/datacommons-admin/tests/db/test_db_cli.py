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
import pytest
from click.testing import CliRunner
from datacommons_admin.admin_cli import admin


def test_init_db_no_terraform(runner: CliRunner) -> None:
    with patch(
        "datacommons_admin.core.terraform.state.shutil.which", return_value=None
    ):
        result = runner.invoke(admin, ["init-db"])
        assert result.exit_code != 0
        assert "Terraform CLI not found" in result.output


def test_init_db_terraform_error(runner: CliRunner) -> None:
    with (
        patch(
            "datacommons_admin.core.terraform.state.shutil.which",
            return_value="terraform",
        ),
        patch(
            "datacommons_admin.core.terraform.state.subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, ["terraform"], stderr="not a terraform dir"
            ),
        ),
    ):
        result = runner.invoke(admin, ["init-db"])
        assert result.exit_code != 0
        assert "Failed to run 'terraform output'" in result.output


@pytest.fixture
def mock_spanner_client():
    """Mocks SpannerClient in db_cli."""
    with patch("datacommons_admin.db.db_cli.SpannerClient") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.mark.usefixtures("mock_terraform_spanner")
def test_init_db_success(
    mock_spanner_client,
    mock_initialize_database,
    runner: CliRunner,
) -> None:
    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code == 0
    assert "Datacommons Admin Init-DB" in result.output
    mock_initialize_database.assert_called_once_with(mock_spanner_client)


@pytest.mark.usefixtures("mock_terraform_spanner")
def test_init_db_migration_failure(
    mock_spanner_client,
    mock_initialize_database,
    runner: CliRunner,
) -> None:
    mock_initialize_database.side_effect = click.ClickException("Initialization failed")

    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code != 0
    assert "Initialization failed" in result.output
