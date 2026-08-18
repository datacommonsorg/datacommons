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
from datacommons_db.clients import (
    DdlResult,
    ExecutionStatus,
    SpannerClient,
)

_bootstrap_module = importlib.import_module(
    "datacommons_db.migrations.migration_scripts.20260817000000_bootstrap"
)
Migration20260817000000Bootstrap = _bootstrap_module.Migration20260817000000Bootstrap
_CREATE_SCHEMA_VERSION_TABLE_DDL = _bootstrap_module._CREATE_SCHEMA_VERSION_TABLE_DDL


@pytest.fixture
def mock_spanner_client():
    client = MagicMock(spec=SpannerClient)
    client.project_id = "test-project"
    client.instance_id = "test-instance"
    client.database_id = "test-db"
    return client


def test_bootstrap_migration_properties():
    migration = Migration20260817000000Bootstrap()
    assert migration.creation_timestamp == "2026-08-17T00:00:00Z"
    assert (
        migration.description
        == "Add SchemaVersion table to bootstrap schema versioning."
    )


def test_bootstrap_migration_creates_schema_version_table(mock_spanner_client):
    # SchemaVersion table does not exist initially
    mock_spanner_client.table_exists.return_value = False
    mock_spanner_client.execute_ddl.return_value = DdlResult(
        status=ExecutionStatus.SUCCESS
    )

    migration = Migration20260817000000Bootstrap()
    migration.upgrade(mock_spanner_client)

    # Verify SchemaVersion DDL was executed
    mock_spanner_client.execute_ddl.assert_called_once_with(
        [_CREATE_SCHEMA_VERSION_TABLE_DDL]
    )


def test_bootstrap_migration_skips_if_schema_version_already_exists(mock_spanner_client):
    # SchemaVersion table already exists
    mock_spanner_client.table_exists.return_value = True

    migration = Migration20260817000000Bootstrap()
    migration.upgrade(mock_spanner_client)

    # DDL execution should be skipped
    mock_spanner_client.execute_ddl.assert_not_called()


def test_bootstrap_migration_schema_version_table_creation_fails(mock_spanner_client):
    mock_spanner_client.table_exists.return_value = False
    mock_spanner_client.execute_ddl.return_value = DdlResult(
        status=ExecutionStatus.ERROR,
        error_message="Failed to create table",
    )

    migration = Migration20260817000000Bootstrap()
    with pytest.raises(
        RuntimeError,
        match="Failed to create SchemaVersion table: Failed to create table",
    ):
        migration.upgrade(mock_spanner_client)
