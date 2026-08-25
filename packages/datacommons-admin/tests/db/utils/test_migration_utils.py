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

from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner
from datacommons_admin.admin_cli import admin
from datacommons_db.clients.spanner_client import ExecutionStatus
from datacommons_db.migrations.migration_runner import MigrationResult


@pytest.fixture
def mock_migration_setup():
    with (
        patch("datacommons_admin.db.db_cli._setup_ingestion_client") as mock_setup,
        patch(
            "datacommons_admin.db.utils.migration_utils._create_migration_runner"
        ) as mock_runner_factory,
    ):
        mock_client = MagicMock()
        mock_setup.return_value = (
            mock_client,
            "mock-proj",
            "mock-instance",
            "mock-db",
        )

        mock_runner = MagicMock()
        mock_runner_factory.return_value = mock_runner

        yield mock_client, mock_runner


@pytest.fixture
def mock_pending_migration() -> MagicMock:
    return MagicMock(
        creation_timestamp="20260817000000", description="Bootstrap migration"
    )


def test_migrate_db_no_pending(
    mock_migration_setup: tuple[MagicMock, MagicMock], runner: CliRunner
) -> None:
    mock_client, mock_runner = mock_migration_setup
    mock_runner.get_pending_migrations.return_value = []

    result = runner.invoke(admin, ["migrate-db"])
    assert result.exit_code == 0
    assert "Database schema is already up-to-date" in result.output
    mock_client.acquire_lock.assert_not_called()


@pytest.mark.parametrize(("args", "input_str"), [(["-y"], None), ([], "y\n")])
def test_migrate_db_apply_success(
    mock_migration_setup: tuple[MagicMock, MagicMock],
    mock_pending_migration: MagicMock,
    runner: CliRunner,
    args: list[str],
    input_str: str | None,
) -> None:
    mock_client, mock_runner = mock_migration_setup
    mock_runner.get_pending_migrations.return_value = [mock_pending_migration]
    mock_runner.run_migrations.return_value = [
        MigrationResult(
            status=ExecutionStatus.SUCCESS,
            creation_timestamp="20260817000000",
            description="Bootstrap migration",
        )
    ]

    result = runner.invoke(admin, ["migrate-db", *args], input=input_str)
    assert result.exit_code == 0
    assert "Found 1 pending schema migration" in result.output
    assert "Applied migration 20260817000000: Bootstrap migration" in result.output
    assert "Successfully applied all schema migrations!" in result.output
    mock_client.acquire_lock.assert_called_once_with(workflow_id="schema-migration")
    mock_runner.run_migrations.assert_called_once()
    mock_client.release_lock.assert_called_once_with(workflow_id="schema-migration")


@pytest.mark.parametrize("input_str", ["n\n", "\n"])
def test_migrate_db_user_cancels(
    mock_migration_setup: tuple[MagicMock, MagicMock],
    mock_pending_migration: MagicMock,
    runner: CliRunner,
    input_str: str,
) -> None:
    mock_client, mock_runner = mock_migration_setup
    mock_runner.get_pending_migrations.return_value = [mock_pending_migration]

    result = runner.invoke(admin, ["migrate-db"], input=input_str)
    assert result.exit_code == 0
    assert "Found 1 pending schema migration" in result.output
    assert (
        "Warning: Schema migrations will modify your Spanner database schema"
        in result.output
    )
    assert "Migration cancelled." in result.output
    mock_client.acquire_lock.assert_not_called()
    mock_runner.run_migrations.assert_not_called()


def test_migrate_db_failure_releases_lock(
    mock_migration_setup: tuple[MagicMock, MagicMock],
    mock_pending_migration: MagicMock,
    runner: CliRunner,
) -> None:
    mock_client, mock_runner = mock_migration_setup
    mock_runner.get_pending_migrations.return_value = [mock_pending_migration]
    mock_runner.run_migrations.side_effect = RuntimeError("DDL operation failed")

    result = runner.invoke(admin, ["migrate-db", "-y"])
    assert result.exit_code != 0
    assert "Failed to apply schema migrations: DDL operation failed" in result.output
    mock_client.acquire_lock.assert_called_once_with(workflow_id="schema-migration")
    mock_client.release_lock.assert_called_once_with(workflow_id="schema-migration")


def test_migrate_db_lock_busy_error(
    mock_migration_setup: tuple[MagicMock, MagicMock],
    mock_pending_migration: MagicMock,
    runner: CliRunner,
) -> None:
    mock_client, mock_runner = mock_migration_setup
    mock_runner.get_pending_migrations.return_value = [mock_pending_migration]
    mock_client.acquire_lock.side_effect = click.ClickException(
        "Could not acquire database lock: Ingestion Helper returned HTTP 503\n"
        "An ingestion workflow may currently be running. "
        "Please wait for active ingestions to finish before running migrations."
    )

    result = runner.invoke(admin, ["migrate-db", "-y"])
    assert result.exit_code != 0
    assert "Ingestion Helper returned HTTP 503" in result.output
    assert (
        "Please wait for active ingestions to finish before running migrations"
        in result.output
    )
    mock_client.release_lock.assert_not_called()
