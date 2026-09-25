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

import pytest
from click.testing import CliRunner
from datacommons_admin.admin_cli import admin
from datacommons_admin.db.db_cli import SpannerCLIContext
from datacommons_admin.db.utils.migration_utils import is_database_initialized
from datacommons_db.clients.spanner_client import ExecutionStatus
from datacommons_db.migrations.migration_runner import MigrationResult


@pytest.fixture
def mock_migration_setup():
    with (
        patch("datacommons_admin.db.db_cli._setup_spanner_client") as mock_setup,
        patch(
            "datacommons_admin.db.utils.migration_utils.MigrationRunner"
        ) as mock_runner_cls,
    ):
        mock_client = MagicMock()
        mock_client.project_id = "mock-proj"
        mock_client.instance_id = "mock-instance"
        mock_client.database_id = "mock-db"

        mock_setup.return_value = SpannerCLIContext(
            client=mock_client,
            project_id="mock-proj",
            instance_id="mock-instance",
            database_id="mock-db",
            region="us-central1",
        )

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

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
    mock_runner.apply_migration.return_value = MigrationResult(
        status=ExecutionStatus.SUCCESS,
        creation_timestamp="20260817000000",
        description="Bootstrap migration",
    )

    result = runner.invoke(admin, ["migrate-db", *args], input=input_str)
    assert result.exit_code == 0
    assert "Found 1 pending schema migration" in result.output
    assert "Applied migration 20260817000000: Bootstrap migration" in result.output
    assert "Successfully applied all schema migrations!" in result.output
    mock_client.acquire_lock.assert_called_once_with(workflow_id="schema-migration")
    mock_runner.apply_migration.assert_called_once()
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
    mock_runner.apply_migration.assert_not_called()


def test_migrate_db_failure_releases_lock(
    mock_migration_setup: tuple[MagicMock, MagicMock],
    mock_pending_migration: MagicMock,
    runner: CliRunner,
) -> None:
    mock_client, mock_runner = mock_migration_setup
    mock_runner.get_pending_migrations.return_value = [mock_pending_migration]
    mock_runner.apply_migration.side_effect = RuntimeError("DDL operation failed")

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
    mock_client.acquire_lock.return_value = False

    result = runner.invoke(admin, ["migrate-db", "-y"])
    assert result.exit_code != 0
    assert "Could not acquire database lock: Lock is currently held" in result.output
    assert (
        "Please wait for active ingestions to finish before running migrations"
        in result.output
    )
    mock_client.release_lock.assert_not_called()


def test_is_database_initialized_true() -> None:
    mock_client = MagicMock()
    mock_client.table_exists.return_value = True

    assert is_database_initialized(mock_client) is True
    mock_client.table_exists.assert_called_once_with("Node")


def test_is_database_initialized_false() -> None:
    mock_client = MagicMock()
    mock_client.table_exists.return_value = False

    assert is_database_initialized(mock_client) is False
    mock_client.table_exists.assert_called_once_with("Node")


def test_is_database_initialized_exception_returns_false() -> None:
    mock_client = MagicMock()
    mock_client.table_exists.side_effect = Exception("Connection error")

    assert is_database_initialized(mock_client) is False


def test_migrate_db_not_initialized_error(
    mock_migration_setup: tuple[MagicMock, MagicMock],
    runner: CliRunner,
) -> None:
    mock_client, mock_runner = mock_migration_setup
    mock_client.table_exists.return_value = False

    result = runner.invoke(admin, ["migrate-db"])
    assert result.exit_code != 0
    assert "Database 'mock-instance/mock-db' has not been initialized" in result.output
    assert "Please run 'datacommons admin init-db'" in result.output
    mock_client.acquire_lock.assert_not_called()
    mock_runner.apply_migration.assert_not_called()


def test_initialize_database_already_initialized_raises(
    mock_migration_setup: tuple[MagicMock, MagicMock],
    runner: CliRunner,
) -> None:
    mock_client, _ = mock_migration_setup
    mock_client.table_exists.return_value = True

    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code != 0
    assert "Database 'mock-instance/mock-db' is already initialized" in result.output
    assert "run 'datacommons admin migrate-db'" in result.output
    mock_client.initialize_database.assert_not_called()


def test_initialize_database_success(
    mock_migration_setup: tuple[MagicMock, MagicMock],
    mock_pending_migration: MagicMock,
    runner: CliRunner,
) -> None:
    mock_client, mock_runner = mock_migration_setup
    # Database is not initialized initially
    mock_client.table_exists.return_value = False
    mock_client.initialize_database.return_value = MagicMock(
        status=ExecutionStatus.SUCCESS
    )

    bootstrap_mig = MagicMock(
        creation_timestamp="2026-08-17T00:00:00Z",
        description="Bootstrap migration",
    )
    subsequent_mig = MagicMock(
        creation_timestamp="20260901000000",
        description="Add feature table",
    )

    mock_runner.get_pending_migrations.return_value = [bootstrap_mig, subsequent_mig]
    mock_runner.apply_migration.side_effect = [
        MigrationResult(
            status=ExecutionStatus.SUCCESS,
            creation_timestamp="2026-08-17T00:00:00Z",
            description="Bootstrap migration",
        ),
        MigrationResult(
            status=ExecutionStatus.SUCCESS,
            creation_timestamp="20260901000000",
            description="Add feature table",
        ),
    ]

    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code == 0
    assert "Initializing baseline schema for Spanner database" in result.output
    assert "Applied baseline schema (schema.sql)" in result.output
    assert "Applying 2 schema migration(s)..." in result.output
    assert (
        "Applied migration 2026-08-17T00:00:00Z: Bootstrap migration" in result.output
    )
    assert "Applied migration 20260901000000: Add feature table" in result.output
    assert "Successfully applied all schema migrations!" in result.output
    mock_client.initialize_database.assert_called_once()
    mock_client.acquire_lock.assert_called_once_with(workflow_id="schema-migration")
    mock_client.release_lock.assert_called_once_with(workflow_id="schema-migration")


def test_initialize_database_failure_raises(
    mock_migration_setup: tuple[MagicMock, MagicMock],
    runner: CliRunner,
) -> None:
    mock_client, _ = mock_migration_setup
    mock_client.table_exists.return_value = False
    mock_client.initialize_database.return_value = MagicMock(
        status=ExecutionStatus.ERROR,
        error_message="Spanner syntax error",
    )

    result = runner.invoke(admin, ["init-db"])
    assert result.exit_code != 0
    assert "Failed to initialize baseline schema: Spanner syntax error" in result.output
