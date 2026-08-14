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

import re
from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest
from datacommons_db.clients import (
    DdlResult,
    DmlResult,
    ExecutionStatus,
    QueryResult,
    SpannerClient,
)
from google.cloud import spanner


class FakeSnapshot:
    """Fake Spanner Snapshot for stateful in-memory querying.

    Simulates the `google.cloud.spanner.Snapshot` context manager returned by
    `database.snapshot()`.

    Storage & Result Format:
    - Queries evaluate against `FakeSpannerDatabase.tables`.
    - Returns rows as a 2D list (`list[list[object]]`), where each outer list
      element is a row, and each inner element is a column value (matching
      Google Cloud Spanner's `StreamedResultSet` iteration format).
    """

    def __init__(self, db: "FakeSpannerDatabase") -> None:
        self.db = db

    def __enter__(self) -> "FakeSnapshot":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    def execute_sql(
        self,
        query: str,
        params: dict[str, object] | None = None,
        param_types: dict[str, object] | None = None,
    ) -> list[list[object]]:
        """Evaluate a SQL query against in-memory table state.

        Args:
            query: SQL query string.
            params: Parameter dictionary (e.g. `{"table_name": "Node"}`).
            param_types: Parameter types dictionary (e.g. `{"table_name": spanner.param_types.STRING}`).

        Returns:
            A list of rows, where each row is a list of column values.
        """
        _ = param_types
        # 1. Querying information_schema.tables
        if "information_schema.tables" in query.lower():
            table_name = str(params.get("table_name")) if params else None
            if table_name and table_name in self.db.tables:
                return [[1]]
            return []

        # 2. Fallback / generic test queries
        if "custom_test_table" in self.db.tables:
            return self.db.tables["custom_test_table"]

        if params and "name" in params:
            return [[f"result_for_{params['name']}"]]

        return []


class FakeTransaction:
    """Fake Spanner Read-Write Transaction for stateful in-memory DML.

    Simulates `google.cloud.spanner_v1.transaction.Transaction` used inside
    `database.run_in_transaction(unit_of_work)`.
    """

    def __init__(self, db: "FakeSpannerDatabase") -> None:
        self.db = db
        self.last_query: str | None = None
        self.last_params: dict[str, object] | None = None
        self.last_param_types: dict[str, object] | None = None

    def execute_update(
        self,
        query: str,
        params: dict[str, object] | None = None,
        param_types: dict[str, object] | None = None,
    ) -> int:
        """Execute a DML update.

        Args:
            query: SQL DML statement string.
            params: Parameter dictionary.
            param_types: Parameter types dictionary.

        Returns:
            The number of rows affected.
        """
        self.last_query = query
        self.last_params = params
        self.last_param_types = param_types
        return 1


class FakeSpannerDatabase:
    """Stateful in-memory Cloud Spanner database test double.

    Provides a black-box test double representing a Cloud Spanner database instance.

    In-Memory Data Structures:
    - `self.tables`: `dict[str, list[dict[str, object]]]`
      Maps a table name (e.g. `"SchemaVersion"`, `"Node"`) to its list of row records.
      Each row record is a dictionary of column names to values:
      `{"Version": 1, "AppliedTimestamp": 1718000000.0, "Description": "Baseline"}`.

    Supported Operations:
    - `update_ddl(statements)`: Parses `CREATE TABLE` and `DROP TABLE` statements using
      regex, mutating `self.tables` and returning a mock LRO operation.
    - `snapshot()`: Returns a `FakeSnapshot` context for read queries.
    - `run_in_transaction(unit_of_work)`: Runs unit of work with a `FakeTransaction`.
    """

    def __init__(
        self, initial_tables: dict[str, list[dict[str, object]]] | None = None
    ) -> None:
        self.tables: dict[str, list[dict[str, object]]] = initial_tables or {}
        self.last_transaction: FakeTransaction | None = None

    def update_ddl(self, ddl_statements: list[str]) -> MagicMock:
        """Apply DDL statements to mutate in-memory schema table definitions."""
        for stmt in ddl_statements:
            cleaned = stmt.strip()
            # Handle CREATE TABLE [IF NOT EXISTS] <name>
            create_match = re.search(
                r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_]+)",
                cleaned,
                re.IGNORECASE,
            )
            if create_match:
                table_name = create_match.group(1)
                self.tables.setdefault(table_name, [])

            # Handle DROP TABLE [IF EXISTS] <name>
            drop_match = re.search(
                r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([A-Za-z0-9_]+)",
                cleaned,
                re.IGNORECASE,
            )
            if drop_match:
                table_name = drop_match.group(1)
                self.tables.pop(table_name, None)

        mock_operation = MagicMock()
        mock_operation.result.return_value = None
        return mock_operation

    def snapshot(self) -> FakeSnapshot:
        """Return a snapshot reader for point-in-time reads."""
        return FakeSnapshot(self)

    def run_in_transaction(
        self, unit_of_work: Callable[[FakeTransaction], object]
    ) -> object:
        """Execute a read-write transaction."""
        self.last_transaction = FakeTransaction(self)
        return unit_of_work(self.last_transaction)


@pytest.fixture(autouse=True)
def fake_spanner_db():
    """Sets up a stateful in-memory Spanner database test double for all tests.

    Intercepts calls to `google.cloud.spanner.Client` so that any `SpannerClient`
    instantiated in tests interacts directly with the in-memory `FakeSpannerDatabase`.
    """
    fake_db = FakeSpannerDatabase()
    with patch(
        "datacommons_db.clients.spanner_client.spanner.Client"
    ) as mock_client_cls:

        def fake_client_factory(project: str, credentials: object = None) -> MagicMock:
            _ = credentials
            mock_client = MagicMock()
            mock_client.project = project
            mock_instance = MagicMock()
            mock_client.instance.return_value = mock_instance
            mock_instance.database.return_value = fake_db
            return mock_client

        mock_client_cls.side_effect = fake_client_factory

        yield fake_db


# ==============================================================================
# Initialization & Validation Tests
# ==============================================================================


def test_init_success():
    client = SpannerClient(
        project_id="test-project",
        instance_id="test-instance",
        database_id="test-db",
    )
    assert client.project_id == "test-project"
    assert client.instance_id == "test-instance"
    assert client.database_id == "test-db"


@pytest.mark.parametrize(
    ("proj", "inst", "db"),
    [
        ("", "inst", "db"),
        ("   ", "inst", "db"),
        ("proj with space", "inst", "db"),
        ("proj/slash", "inst", "db"),
        (None, "inst", "db"),
        ("proj", "", "db"),
        ("proj", "   ", "db"),
        ("proj", "inst with space", "db"),
        ("proj", "inst$", "db"),
        ("proj", None, "db"),
        ("proj", "inst", ""),
        ("proj", "inst", "   "),
        ("proj", "inst", "db;drop table"),
        ("proj", "inst", None),
    ],
)
def test_init_validation_errors(proj: str | None, inst: str, db: str):
    with pytest.raises(
        ValueError, match="Invalid (project_id|instance_id|database_id)"
    ):
        SpannerClient(project_id=proj, instance_id=inst, database_id=db)


# ==============================================================================
# Table Existence & DDL Tests
# ==============================================================================


def test_table_exists_false():
    client = SpannerClient("proj", "inst", "db")
    assert client.table_exists("NonExistentTable") is False


def test_table_exists_true():
    client = SpannerClient("proj", "inst", "db")
    result = client.execute_ddl(
        ["CREATE TABLE Node (subject_id STRING(64)) PRIMARY KEY (subject_id)"]
    )
    assert isinstance(result, DdlResult)
    assert result.status == ExecutionStatus.SUCCESS
    assert client.table_exists("Node") is True


def test_execute_ddl_multiple_statements():
    client = SpannerClient("proj", "inst", "db")
    result = client.execute_ddl(
        [
            "CREATE TABLE Node (subject_id STRING(64)) PRIMARY KEY (subject_id)",
            "CREATE TABLE Edge (predicate STRING(64)) PRIMARY KEY (predicate)",
        ]
    )
    assert result.status == ExecutionStatus.SUCCESS
    assert client.table_exists("Node") is True
    assert client.table_exists("Edge") is True


def test_execute_ddl_single_statement():
    client = SpannerClient("proj", "inst", "db")
    result = client.execute_ddl(
        ["CREATE TABLE SingleTable (id INT64) PRIMARY KEY (id)"]
    )
    assert result.status == ExecutionStatus.SUCCESS
    assert client.table_exists("SingleTable") is True


def test_execute_ddl_drop_table():
    client = SpannerClient("proj", "inst", "db")
    result1 = client.execute_ddl(
        ["CREATE TABLE Edge (predicate STRING(64)) PRIMARY KEY (predicate)"]
    )
    assert result1.status == ExecutionStatus.SUCCESS
    assert client.table_exists("Edge") is True

    result2 = client.execute_ddl(["DROP TABLE Edge"])
    assert result2.status == ExecutionStatus.SUCCESS
    assert client.table_exists("Edge") is False


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        "   ",
        "Table with spaces",
        "Table;DROP TABLE users;--",
        "Table-With-Dashes",
        "Table$Name",
    ],
)
def test_table_exists_invalid_name(invalid_name: str):
    client = SpannerClient("proj", "inst", "db")
    with pytest.raises(ValueError, match="Invalid table name"):
        client.table_exists(invalid_name)


def test_execute_ddl_list():
    client = SpannerClient("proj", "inst", "db")
    result = client.execute_ddl(
        [
            "CREATE TABLE TableA (id INT64) PRIMARY KEY (id)",
            "CREATE TABLE TableB (id INT64) PRIMARY KEY (id)",
        ]
    )
    assert result.status == ExecutionStatus.SUCCESS
    assert client.table_exists("TableA") is True
    assert client.table_exists("TableB") is True


def test_execute_ddl_empty_list():
    client = SpannerClient("proj", "inst", "db")
    result = client.execute_ddl([])
    assert result.status == ExecutionStatus.SUCCESS


@pytest.mark.parametrize(
    "invalid_ddl",
    [
        "CREATE TABLE SingleTable (id INT64) PRIMARY KEY (id)",
        "",
        123,
        None,
    ],
)
def test_execute_ddl_invalid_type(invalid_ddl: object):
    client = SpannerClient("proj", "inst", "db")
    result = client.execute_ddl(invalid_ddl)
    assert result.status == ExecutionStatus.ERROR
    assert "must be a list of str" in result.error_message


def test_execute_ddl_error(fake_spanner_db: FakeSpannerDatabase):
    client = SpannerClient("proj", "inst", "db")
    fake_spanner_db.update_ddl = MagicMock(
        side_effect=RuntimeError("Spanner DDL execution failed")
    )
    result = client.execute_ddl(["CREATE TABLE ErrorTable (id INT64) PRIMARY KEY (id)"])
    assert result.status == ExecutionStatus.ERROR
    assert "Spanner DDL execution failed" in result.error_message


# ==============================================================================
# DML & Query Execution Tests
# ==============================================================================


def test_execute_dml_with_params(fake_spanner_db: FakeSpannerDatabase):
    client = SpannerClient("proj", "inst", "db")
    params = {"val": "test_val"}
    param_types = {"val": spanner.param_types.STRING}

    result = client.execute_dml(
        "UPDATE Node SET value = @val WHERE true",
        params=params,
        param_types=param_types,
    )
    assert isinstance(result, DmlResult)
    assert result.status == ExecutionStatus.SUCCESS
    assert result.rows_affected == 1
    assert result.error_message is None
    assert fake_spanner_db.last_transaction is not None
    assert (
        fake_spanner_db.last_transaction.last_query
        == "UPDATE Node SET value = @val WHERE true"
    )
    assert fake_spanner_db.last_transaction.last_params == params
    assert fake_spanner_db.last_transaction.last_param_types == param_types


def test_execute_dml_error(fake_spanner_db: FakeSpannerDatabase):
    client = SpannerClient("proj", "inst", "db")
    fake_spanner_db.run_in_transaction = MagicMock(
        side_effect=RuntimeError("Transaction failed")
    )
    result = client.execute_dml("UPDATE Node SET value = 'test'")
    assert isinstance(result, DmlResult)
    assert result.status == ExecutionStatus.ERROR
    assert result.rows_affected == 0
    assert "Transaction failed" in result.error_message


def test_execute_query_with_params():
    client = SpannerClient("proj", "inst", "db")
    params = {"name": "test_node"}
    param_types = {"name": spanner.param_types.STRING}

    result = client.execute_query(
        "SELECT 1 WHERE name = @name",
        params=params,
        param_types=param_types,
    )
    assert isinstance(result, QueryResult)
    assert result.status == ExecutionStatus.SUCCESS
    assert result.rows == [["result_for_test_node"]]
    assert result.error_message is None


def test_execute_query_custom_table(fake_spanner_db: FakeSpannerDatabase):
    fake_spanner_db.tables["custom_test_table"] = [["row1", 10], ["row2", 20]]
    client = SpannerClient("proj", "inst", "db")

    result = client.execute_query("SELECT name, count FROM custom_test_table")
    assert isinstance(result, QueryResult)
    assert result.status == ExecutionStatus.SUCCESS
    assert result.rows == [["row1", 10], ["row2", 20]]
    assert result.error_message is None


def test_execute_query_error(fake_spanner_db: FakeSpannerDatabase):
    client = SpannerClient("proj", "inst", "db")
    fake_spanner_db.snapshot = MagicMock(
        side_effect=RuntimeError("Snapshot read failed")
    )
    result = client.execute_query("SELECT 1")
    assert isinstance(result, QueryResult)
    assert result.status == ExecutionStatus.ERROR
    assert result.rows == []
    assert "Snapshot read failed" in result.error_message
