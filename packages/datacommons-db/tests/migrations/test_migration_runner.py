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

import importlib
from unittest.mock import MagicMock

import pytest
from datacommons_db.clients import ExecutionStatus, QueryResult, SpannerClient
from datacommons_db.migrations import MigrationRunner, SchemaMigration
from google.cloud import spanner

_bootstrap_module = importlib.import_module(
    "datacommons_db.migrations.migration_scripts.20260817000000_bootstrap"
)
MigrationBootstrap = _bootstrap_module.Migration


class DummyMigration(SchemaMigration):
    creation_timestamp: str = "2026-08-17T00:00:00Z"
    description: str = "dummy"

    def __init__(
        self,
        creation_timestamp: str,
        desc: str = "dummy",
        *,
        should_fail: bool = False,
    ) -> None:
        self.creation_timestamp = creation_timestamp
        self.description = desc
        self._should_fail = should_fail
        self.rolled_forward = False

    def upgrade(self, spanner_client: SpannerClient) -> None:
        _ = spanner_client
        if self._should_fail:
            raise RuntimeError(
                f"Migration {self.creation_timestamp} failed deliberately"
            )
        self.rolled_forward = True


@pytest.fixture
def mock_spanner_client():
    client = MagicMock(spec=SpannerClient)
    client.project_id = "test-project"
    client.instance_id = "test-instance"
    client.database_id = "test-db"
    return client


# ==============================================================================
# Migration Sequence Validation Tests
# ==============================================================================


def test_validate_migrations_empty():
    assert MigrationRunner.validate_migrations([]) == []


def test_validate_migrations_valid_sequence():
    m1 = DummyMigration("2026-08-17T10:00:00Z")
    m2 = DummyMigration("2026-08-17T11:00:00Z")
    m3 = DummyMigration("2026-08-17T12:00:00Z")

    result = MigrationRunner.validate_migrations([m3, m1, m2])
    assert result == [m1, m2, m3]


def test_validate_migrations_duplicate_timestamp():
    m1 = DummyMigration("2026-08-17T10:00:00Z", desc="first")
    m2 = DummyMigration("2026-08-17T10:00:00Z", desc="second")
    with pytest.raises(
        ValueError,
        match="Duplicate migration creation_timestamp detected: 2026-08-17T10:00:00Z",
    ):
        MigrationRunner.validate_migrations([m1, m2])


# ==============================================================================
# Discovery & Applied Migrations Tests
# ==============================================================================


def test_discover_migrations(mock_spanner_client):
    runner = MigrationRunner(mock_spanner_client)
    assert len(runner.migrations) >= 1
    assert isinstance(runner.migrations[0], MigrationBootstrap)
    assert runner.migrations[0].creation_timestamp == "2026-08-17T00:00:00Z"


def test_get_applied_migrations_table_missing(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = False
    runner = MigrationRunner(mock_spanner_client, migrations=[])

    assert runner.get_applied_migrations() == set()
    mock_spanner_client.table_exists.assert_called_once_with("SchemaMigrations")


def test_get_applied_migrations_empty_table(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = True
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.SUCCESS,
        rows=[],
    )
    runner = MigrationRunner(mock_spanner_client, migrations=[])

    assert runner.get_applied_migrations() == set()


def test_get_applied_migrations_with_records(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = True
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.SUCCESS,
        rows=[["2026-08-17T10:00:00Z"], ["2026-08-17T11:00:00Z"]],
    )
    runner = MigrationRunner(mock_spanner_client, migrations=[])

    assert runner.get_applied_migrations() == {
        "2026-08-17T10:00:00Z",
        "2026-08-17T11:00:00Z",
    }
    mock_spanner_client.execute_query.assert_called_once()
    query_arg = mock_spanner_client.execute_query.call_args[0][0]
    assert "SELECT CreationTimestamp FROM SchemaMigrations" in query_arg


def test_get_applied_migrations_malformed_row(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = True
    # Test that empty row [] raises RuntimeError
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.SUCCESS,
        rows=[[]],
    )
    runner = MigrationRunner(mock_spanner_client, migrations=[])

    with pytest.raises(
        RuntimeError,
        match="Invalid or non-indexable row format in SchemaMigrations query results",
    ):
        runner.get_applied_migrations()


def test_get_applied_migrations_query_error(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = True
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.ERROR,
        error_message="Query error",
    )
    runner = MigrationRunner(mock_spanner_client, migrations=[])

    with pytest.raises(
        RuntimeError, match="Failed to query SchemaMigrations table: Query error"
    ):
        runner.get_applied_migrations()


# ==============================================================================
# Pending Migrations & Execution Tests
# ==============================================================================


def test_get_pending_migrations(mock_spanner_client):
    m1 = DummyMigration("2026-08-17T10:00:00Z")
    m2 = DummyMigration("2026-08-17T11:00:00Z")
    m3 = DummyMigration("2026-08-17T12:00:00Z")

    runner = MigrationRunner(mock_spanner_client, migrations=[m1, m2, m3])

    # Case 1: table missing -> none applied -> all pending
    mock_spanner_client.table_exists.return_value = False
    assert runner.get_pending_migrations() == [m1, m2, m3]

    # Case 2: m1 applied -> m2 and m3 pending
    mock_spanner_client.table_exists.return_value = True
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.SUCCESS,
        rows=[["2026-08-17T10:00:00Z"]],
    )
    assert runner.get_pending_migrations() == [m2, m3]

    # Case 3: all applied -> none pending
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.SUCCESS,
        rows=[
            ["2026-08-17T10:00:00Z"],
            ["2026-08-17T11:00:00Z"],
            ["2026-08-17T12:00:00Z"],
        ],
    )
    assert runner.get_pending_migrations() == []

    # Case 4: m2 applied -> m1 and m3 pending
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.SUCCESS,
        rows=[["2026-08-17T11:00:00Z"]],
    )
    assert runner.get_pending_migrations() == [m1, m3]


def test_apply_migration_success(mock_spanner_client):
    m = DummyMigration("2026-08-17T10:00:00Z", desc="Baseline")
    mock_spanner_client.execute_dml.return_value = MagicMock(
        status=ExecutionStatus.SUCCESS,
        rows_affected=1,
    )

    runner = MigrationRunner(mock_spanner_client, migrations=[m])
    runner.apply_migration(m)

    assert m.rolled_forward is True
    mock_spanner_client.execute_dml.assert_called_once()
    query_arg, kwargs = (
        mock_spanner_client.execute_dml.call_args[0][0],
        mock_spanner_client.execute_dml.call_args[1],
    )
    assert "INSERT INTO SchemaMigrations" in query_arg
    assert kwargs["params"] == {
        "creation_timestamp": "2026-08-17T10:00:00Z",
        "description": "Baseline",
    }
    assert kwargs["param_types"] == {
        "creation_timestamp": spanner.param_types.STRING,
        "description": spanner.param_types.STRING,
    }


def test_apply_migration_upgrade_failure(mock_spanner_client):
    m = DummyMigration("2026-08-17T10:00:00Z", should_fail=True)
    runner = MigrationRunner(mock_spanner_client, migrations=[m])

    with pytest.raises(
        RuntimeError, match="Migration 2026-08-17T10:00:00Z failed deliberately"
    ):
        runner.apply_migration(m)

    mock_spanner_client.execute_dml.assert_not_called()


def test_apply_migration_dml_failure(mock_spanner_client):
    m = DummyMigration("2026-08-17T10:00:00Z")
    mock_spanner_client.execute_dml.return_value = MagicMock(
        status=ExecutionStatus.ERROR,
        error_message="DML insert failed",
    )

    runner = MigrationRunner(mock_spanner_client, migrations=[m])

    with pytest.raises(
        RuntimeError,
        match="Failed to record migration 2026-08-17T10:00:00Z in SchemaMigrations: DML insert failed",
    ):
        runner.apply_migration(m)


def test_record_applied_migration_success(mock_spanner_client):
    mock_spanner_client.execute_dml.return_value = MagicMock(
        status=ExecutionStatus.SUCCESS,
        rows_affected=1,
    )
    runner = MigrationRunner(mock_spanner_client, migrations=[])
    runner.record_applied_migration(
        creation_timestamp="2026-08-17T11:00:00Z", description="Add table"
    )

    mock_spanner_client.execute_dml.assert_called_once()
    query_arg, kwargs = (
        mock_spanner_client.execute_dml.call_args[0][0],
        mock_spanner_client.execute_dml.call_args[1],
    )
    assert "INSERT INTO SchemaMigrations" in query_arg
    assert kwargs["params"] == {
        "creation_timestamp": "2026-08-17T11:00:00Z",
        "description": "Add table",
    }


def test_record_applied_migration_failure(mock_spanner_client):
    mock_spanner_client.execute_dml.return_value = MagicMock(
        status=ExecutionStatus.ERROR,
        error_message="Connection lost",
    )
    runner = MigrationRunner(mock_spanner_client, migrations=[])
    with pytest.raises(
        RuntimeError,
        match="Failed to record migration 2026-08-17T11:00:00Z in SchemaMigrations: Connection lost",
    ):
        runner.record_applied_migration(
            creation_timestamp="2026-08-17T11:00:00Z", description="Add table"
        )


def test_get_latest_applied_migration_empty(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = False
    runner = MigrationRunner(mock_spanner_client, migrations=[])

    assert runner.get_latest_applied_migration() is None


def test_get_latest_applied_migration_with_records(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = True
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.SUCCESS,
        rows=[
            ["2026-08-17T10:00:00Z"],
            ["2026-08-17T12:00:00Z"],
            ["2026-08-17T11:00:00Z"],
        ],
    )
    runner = MigrationRunner(mock_spanner_client, migrations=[])

    assert runner.get_latest_applied_migration() == "2026-08-17T12:00:00Z"


def test_run_migrations_all_applied(mock_spanner_client):
    m1 = DummyMigration("2026-08-17T10:00:00Z")
    m2 = DummyMigration("2026-08-17T11:00:00Z")

    mock_spanner_client.table_exists.return_value = False
    mock_spanner_client.execute_dml.return_value = MagicMock(
        status=ExecutionStatus.SUCCESS,
        rows_affected=1,
    )

    runner = MigrationRunner(mock_spanner_client, migrations=[m1, m2])
    applied = runner.run_migrations()

    assert applied == [m1, m2]
    assert m1.rolled_forward is True
    assert m2.rolled_forward is True
    assert mock_spanner_client.execute_dml.call_count == 2


def test_run_migrations_already_up_to_date(mock_spanner_client):
    m1 = DummyMigration("2026-08-17T10:00:00Z")

    mock_spanner_client.table_exists.return_value = True
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.SUCCESS,
        rows=[["2026-08-17T10:00:00Z"]],
    )

    runner = MigrationRunner(mock_spanner_client, migrations=[m1])
    applied = runner.run_migrations()

    assert applied == []
    assert m1.rolled_forward is False
    mock_spanner_client.execute_dml.assert_not_called()


def test_run_migrations_stops_on_first_error(mock_spanner_client, caplog):
    m1 = DummyMigration("2026-08-17T10:00:00Z", should_fail=True)
    m2 = DummyMigration("2026-08-17T11:00:00Z")

    mock_spanner_client.table_exists.return_value = False

    runner = MigrationRunner(mock_spanner_client, migrations=[m1, m2])

    with (
        caplog.at_level("ERROR"),
        pytest.raises(
            RuntimeError,
            match="Migration 2026-08-17T10:00:00Z failed deliberately",
        ),
    ):
        runner.run_migrations()

    assert m1.rolled_forward is False
    assert m2.rolled_forward is False
    mock_spanner_client.execute_dml.assert_not_called()
    assert "Migration 2026-08-17T10:00:00Z failed" in caplog.text
    assert "Halting migration sequence" in caplog.text
