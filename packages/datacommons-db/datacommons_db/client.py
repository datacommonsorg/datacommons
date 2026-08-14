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
from typing import Any

from google.auth.credentials import Credentials
from google.cloud import spanner
from google.cloud.spanner_v1.transaction import Transaction

_SCHEMA_VERSION_TABLE_NAME = "SchemaVersion"
_TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
_RESOURCE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_resource_id(name: str, value: object) -> None:
    """Validate that a GCP / Spanner resource ID matches expected identifier patterns."""
    if not isinstance(value, str) or not value or not _RESOURCE_ID_PATTERN.match(value):
        raise ValueError(
            f"Invalid {name} '{value}'. Must be a non-empty string containing only alphanumeric characters, underscores, and hyphens."
        )


class SpannerClient:
    """Client for Cloud Spanner schema management, DDL execution, and version tracking."""

    def __init__(
        self,
        project_id: str,
        instance_id: str,
        database_id: str,
        credentials: Credentials | None = None,
    ) -> None:
        """Initialize the SpannerClient.

        Args:
            project_id: GCP project ID.
            instance_id: Cloud Spanner instance ID.
            database_id: Cloud Spanner database ID.
            credentials: Optional Google Cloud credentials object.
        """
        _validate_resource_id("project_id", project_id)
        _validate_resource_id("instance_id", instance_id)
        _validate_resource_id("database_id", database_id)

        self.project_id = project_id
        self.instance_id = instance_id
        self.database_id = database_id

        self.client = spanner.Client(project=self.project_id, credentials=credentials)
        self.instance = self.client.instance(self.instance_id)
        self.database = self.instance.database(self.database_id)

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the Cloud Spanner database.

        Args:
            table_name: The table name to check.

        Returns:
            True if the table exists, False otherwise.
        """
        if not table_name or not _TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(
                f"Invalid table name '{table_name}'. Table names must match {_TABLE_NAME_PATTERN.pattern}"
            )

        query = (
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = '' AND table_name = @table_name LIMIT 1"
        )
        params = {"table_name": table_name}
        param_types = {"table_name": spanner.param_types.STRING}

        with self.database.snapshot() as snapshot:
            for _ in snapshot.execute_sql(
                query, params=params, param_types=param_types
            ):
                return True
            return False

    def schema_version_table_exists(self) -> bool:
        """Check if the SchemaVersion table exists in Cloud Spanner."""
        return self.table_exists(_SCHEMA_VERSION_TABLE_NAME)

    def get_schema_version(self) -> int:
        """Get the current schema version from the SchemaVersion table.

        Returns:
            The current active integer schema version, or 0 if SchemaVersion does not exist.
        """
        if not self.schema_version_table_exists():
            return 0

        # The version with the latest applied timestamp is the current version.
        query = (
            f"SELECT Version FROM {_SCHEMA_VERSION_TABLE_NAME} "  # noqa: S608
            "ORDER BY AppliedTimestamp DESC LIMIT 1"
        )
        with self.database.snapshot() as snapshot:
            for row in snapshot.execute_sql(query):
                return int(row[0]) if row[0] is not None else 0
            return 0

    def update_schema_version(self, version: int, description: str) -> None:
        """Insert a newly applied schema version into SchemaVersion.

        Args:
            version: The integer schema version applied.
            description: Description of the schema migration.
        """
        if not isinstance(version, int) or version < 0:
            raise ValueError(f"Version must be a non-negative integer, got {version}")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("Description must be a non-empty string.")

        query = (
            f"INSERT INTO {_SCHEMA_VERSION_TABLE_NAME} (Version, AppliedTimestamp, Description) "  # noqa: S608
            "VALUES (@version, PENDING_COMMIT_TIMESTAMP(), @description)"
        )
        params = {"version": version, "description": description.strip()}
        param_types = {
            "version": spanner.param_types.INT64,
            "description": spanner.param_types.STRING,
        }

        self.execute_dml(query, params=params, param_types=param_types)

    def set_schema_version(self, version: int, description: str) -> None:
        """Alias for update_schema_version."""
        self.update_schema_version(version, description)

    def execute_ddl(self, ddl_statements: str | list[str]) -> None:
        """Execute DDL statements and wait for completion.

        Handles operations like CREATE TABLE, ALTER TABLE, etc.

        Args:
            ddl_statements: A single DDL string (optionally multi-statement separated by ;)
                           or a list of DDL statement strings.
        """
        statements: list[str] = []
        if isinstance(ddl_statements, str):
            for stmt in ddl_statements.split(";"):
                cleaned = stmt.strip()
                if cleaned:
                    statements.append(cleaned)
        elif isinstance(ddl_statements, list):
            for stmt in ddl_statements:
                if isinstance(stmt, str):
                    cleaned = stmt.strip()
                    if cleaned:
                        statements.append(cleaned)
        else:
            raise TypeError("ddl_statements must be a str or a list of str.")

        if not statements:
            return

        operation = self.database.update_ddl(statements)
        operation.result()

    def execute_dml(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        param_types: dict[str, Any] | None = None,
    ) -> int:
        """Execute a DML statement inside a Spanner read-write transaction.

        Handles operations like INSERT, UPDATE, DELETE

        Args:
            query: The parameterized DML statement.
            params: Dictionary of parameters.
            param_types: Dictionary of parameter types.

        Returns:
            The number of rows modified.
        """

        def _unit_of_work(transaction: Transaction) -> int:
            return transaction.execute_update(
                query, params=params, param_types=param_types
            )

        return self.database.run_in_transaction(_unit_of_work)

    def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        param_types: dict[str, Any] | None = None,
    ) -> list[list[Any]]:
        """Execute a read query within a snapshot transaction.

        Handles operations like SELECT.

        Args:
            query: The parameterized SQL query.
            params: Dictionary of parameters.
            param_types: Dictionary of parameter types.

        Returns:
            A list of result rows (each row as a list).
        """
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query, params=params, param_types=param_types
            )
            return [list(row) for row in results]
