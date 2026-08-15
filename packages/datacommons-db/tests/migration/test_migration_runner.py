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

from unittest.mock import MagicMock

import pytest
from datacommons_db.clients import ExecutionStatus, QueryResult, SpannerClient
from datacommons_db.migrations import MigrationRunner, SchemaMigration
from datacommons_db.migrations.migration_scripts.migration_0001_bootstrap import (
    Migration0001Bootstrap,
)
from google.cloud import spanner


class DummyMigration(SchemaMigration):
    source_version: int = 0
    target_version: int = 1
    description: str = "dummy"

    def __init__(
        self,
        source: int,
        target: int,
        desc: str = "dummy",
        *,
        should_fail: bool = False,
    ) -> None:
        self.source_version = source
        self.target_version = target
        self.description = desc
        self._should_fail = should_fail
        self.rolled_forward = False

    def roll_forward(self, spanner_client: SpannerClient) -> None:
        _ = spanner_client
        if self._should_fail:
            raise RuntimeError(
                f"Migration {self.source_version}->{self.target_version} failed deliberately"
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
    m1 = DummyMigration(0, 1)
    m2 = DummyMigration(1, 2)
    m3 = DummyMigration(2, 3)

    result = MigrationRunner.validate_migrations([m3, m1, m2])
    assert result == [m1, m2, m3]


def test_validate_migrations_non_zero_start_valid():
    m1 = DummyMigration(3, 4)
    m2 = DummyMigration(4, 5)
    result = MigrationRunner.validate_migrations([m2, m1])
    assert result == [m1, m2]


def test_validate_migrations_invalid_step_increment():
    m = DummyMigration(0, 2)
    with pytest.raises(ValueError, match="must have target_version 1, but found 2"):
        MigrationRunner.validate_migrations([m])


def test_validate_migrations_duplicate_source_version():
    m1 = DummyMigration(0, 1, desc="first")
    m2 = DummyMigration(0, 1, desc="second")
    with pytest.raises(ValueError, match="Duplicate source_version 0"):
        MigrationRunner.validate_migrations([m1, m2])


def test_validate_migrations_discontinuous_sequence():
    m1 = DummyMigration(0, 1)
    m2 = DummyMigration(2, 3)
    with pytest.raises(ValueError, match="Discontinuous migration sequence: gap between target_version 1 and source_version 2"):
        MigrationRunner.validate_migrations([m1, m2])


# ==============================================================================
# Discovery & Current Version Tests
# ==============================================================================


def test_discover_migrations(mock_spanner_client):
    runner = MigrationRunner(mock_spanner_client)
    assert len(runner.migrations) >= 1
    assert isinstance(runner.migrations[0], Migration0001Bootstrap)
    assert runner.migrations[0].source_version == 0
    assert runner.migrations[0].target_version == 1


def test_get_current_version_table_missing(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = False
    runner = MigrationRunner(mock_spanner_client, migrations=[])

    assert runner.get_current_version() == 0
    mock_spanner_client.table_exists.assert_called_once_with("SchemaVersion")


def test_get_current_version_empty_table(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = True
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.SUCCESS,
        rows=[],
    )
    runner = MigrationRunner(mock_spanner_client, migrations=[])

    assert runner.get_current_version() == 0


def test_get_current_version_with_version(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = True
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.SUCCESS,
        rows=[[3]],
    )
    runner = MigrationRunner(mock_spanner_client, migrations=[])

    assert runner.get_current_version() == 3


def test_get_current_version_query_error(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = True
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.ERROR,
        error_message="Query error",
    )
    runner = MigrationRunner(mock_spanner_client, migrations=[])

    with pytest.raises(RuntimeError, match="Failed to query SchemaVersion table: Query error"):
        runner.get_current_version()


# ==============================================================================
# Pending Migrations & Execution Tests
# ==============================================================================


def test_get_pending_migrations(mock_spanner_client):
    m1 = DummyMigration(0, 1)
    m2 = DummyMigration(1, 2)
    m3 = DummyMigration(2, 3)

    runner = MigrationRunner(mock_spanner_client, migrations=[m1, m2, m3])

    # Case 1: current version 0
    assert runner.get_pending_migrations(current_version=0) == [m1, m2, m3]

    # Case 2: current version 1
    assert runner.get_pending_migrations(current_version=1) == [m2, m3]

    # Case 3: current version 3
    assert runner.get_pending_migrations(current_version=3) == []


def test_apply_migration_success(mock_spanner_client):
    m = DummyMigration(0, 1, desc="Baseline")
    mock_spanner_client.execute_dml.return_value = MagicMock(
        status=ExecutionStatus.SUCCESS,
        rows_affected=1,
    )

    runner = MigrationRunner(mock_spanner_client, migrations=[m])
    runner.apply_migration(m)

    assert m.rolled_forward is True
    mock_spanner_client.execute_dml.assert_called_once()
    query_arg, kwargs = mock_spanner_client.execute_dml.call_args[0][0], mock_spanner_client.execute_dml.call_args[1]
    assert "INSERT INTO SchemaVersion" in query_arg
    assert kwargs["params"] == {"version": 1, "description": "Baseline"}
    assert kwargs["param_types"] == {
        "version": spanner.param_types.INT64,
        "description": spanner.param_types.STRING,
    }


def test_apply_migration_roll_forward_failure(mock_spanner_client):
    m = DummyMigration(0, 1, should_fail=True)
    runner = MigrationRunner(mock_spanner_client, migrations=[m])

    with pytest.raises(RuntimeError, match="Migration 0->1 failed deliberately"):
        runner.apply_migration(m)

    mock_spanner_client.execute_dml.assert_not_called()


def test_apply_migration_dml_failure(mock_spanner_client):
    m = DummyMigration(0, 1)
    mock_spanner_client.execute_dml.return_value = MagicMock(
        status=ExecutionStatus.ERROR,
        error_message="DML insert failed",
    )

    runner = MigrationRunner(mock_spanner_client, migrations=[m])

    with pytest.raises(
        RuntimeError,
        match="Failed to record migration version 1 in SchemaVersion: DML insert failed",
    ):
        runner.apply_migration(m)


def test_run_migrations_all_applied(mock_spanner_client):
    m1 = DummyMigration(0, 1)
    m2 = DummyMigration(1, 2)

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
    m1 = DummyMigration(0, 1)

    mock_spanner_client.table_exists.return_value = True
    mock_spanner_client.execute_query.return_value = QueryResult(
        status=ExecutionStatus.SUCCESS,
        rows=[[1]],
    )

    runner = MigrationRunner(mock_spanner_client, migrations=[m1])
    applied = runner.run_migrations()

    assert applied == []
    assert m1.rolled_forward is False
    mock_spanner_client.execute_dml.assert_not_called()


def test_run_migrations_stops_on_first_error(mock_spanner_client):
    m1 = DummyMigration(0, 1, should_fail=True)
    m2 = DummyMigration(1, 2)

    mock_spanner_client.table_exists.return_value = False

    runner = MigrationRunner(mock_spanner_client, migrations=[m1, m2])

    with pytest.raises(RuntimeError, match="Migration 0->1 failed deliberately"):
        runner.run_migrations()

    assert m1.rolled_forward is False
    assert m2.rolled_forward is False
    mock_spanner_client.execute_dml.assert_not_called()
