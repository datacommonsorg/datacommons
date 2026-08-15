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
from datacommons_db.clients import (
    DdlResult,
    ExecutionStatus,
    SpannerClient,
)
from datacommons_db.migrations.migration_scripts.migration_0001_bootstrap import (
    _CREATE_SCHEMA_VERSION_TABLE_DDL,
    Migration0001Bootstrap,
)


@pytest.fixture
def mock_spanner_client():
    client = MagicMock(spec=SpannerClient)
    client.project_id = "test-project"
    client.instance_id = "test-instance"
    client.database_id = "test-db"
    return client


def test_migration_0001_properties():
    migration = Migration0001Bootstrap()
    assert migration.source_version == 0
    assert migration.target_version == 1
    assert migration.description == "Add SchemaVersion table to bootstrap schema versioning."


def test_migration_0001_roll_backward_not_implemented(mock_spanner_client):
    migration = Migration0001Bootstrap()
    with pytest.raises(NotImplementedError, match="Rollback not implemented"):
        migration.roll_backward(mock_spanner_client)


def test_migration_0001_creates_schema_version_table(mock_spanner_client):
    # SchemaVersion table does not exist initially
    mock_spanner_client.table_exists.return_value = False
    mock_spanner_client.execute_ddl.return_value = DdlResult(status=ExecutionStatus.SUCCESS)

    migration = Migration0001Bootstrap()
    migration.roll_forward(mock_spanner_client)

    # Verify SchemaVersion DDL was executed
    mock_spanner_client.execute_ddl.assert_called_once_with(
        [_CREATE_SCHEMA_VERSION_TABLE_DDL]
    )


def test_migration_0001_skips_if_schema_version_already_exists(mock_spanner_client):
    # SchemaVersion table already exists
    mock_spanner_client.table_exists.return_value = True

    migration = Migration0001Bootstrap()
    migration.roll_forward(mock_spanner_client)

    # DDL execution should be skipped
    mock_spanner_client.execute_ddl.assert_not_called()


def test_migration_0001_schema_version_table_creation_fails(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = False
    mock_spanner_client.execute_ddl.return_value = DdlResult(
        status=ExecutionStatus.ERROR,
        error_message="Failed to create table",
    )

    migration = Migration0001Bootstrap()
    with pytest.raises(
        RuntimeError,
        match="Failed to create SchemaVersion table: Failed to create table",
    ):
        migration.roll_forward(mock_spanner_client)
