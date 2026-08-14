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

from collections.abc import Iterator
from typing import Any

from google.auth.credentials import Credentials
from google.cloud import spanner
from google.cloud.spanner_v1.transaction import Transaction

from datacommons_db.utils.validators import (
    validate_resource_id,
    validate_table_name,
)


class SpannerClient:
    """Client for Cloud Spanner operations, DDL execution, and query execution."""

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
        validate_resource_id("project_id", project_id)
        validate_resource_id("instance_id", instance_id)
        validate_resource_id("database_id", database_id)

        self.project_id = project_id
        self.instance_id = instance_id
        self.database_id = database_id

        self.client = spanner.Client(project=project_id, credentials=credentials)
        self.instance = self.client.instance(self.instance_id)
        self.database = self.instance.database(self.database_id)

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the Cloud Spanner database.

        Args:
            table_name: The table name to check.

        Returns:
            True if the table exists, False otherwise.
        """
        validate_table_name(table_name)

        query = (
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema IN ('', 'public') AND table_name = @table_name LIMIT 1"
        )

        params = {"table_name": table_name}
        param_types = {"table_name": spanner.param_types.STRING}

        with self.database.snapshot() as snapshot:
            for _ in snapshot.execute_sql(
                query, params=params, param_types=param_types
            ):
                return True
            return False

    def execute_ddl(self, ddl_statements: str | list[str]) -> None:
        """Execute DDL statements and wait for completion.

        Handles operations like CREATE TABLE, ALTER TABLE, etc.

        Args:
            ddl_statements: A single DDL statement string or a list of DDL statement strings.
        """
        if isinstance(ddl_statements, str):
            statements = [ddl_statements]
        elif isinstance(ddl_statements, list):
            statements = ddl_statements
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

    def _execute_query_stream(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        param_types: dict[str, Any] | None = None,
    ) -> Iterator[list[Any]]:
        """Stream query results lazily row-by-row from a point-in-time snapshot.
        This prevents OOM errors when querying large tables.

        Args:
            query: The parameterized SQL query string.
            params: Dictionary of query parameters.
            param_types: Dictionary of parameter types.

        Yields:
            Rows as lists of column values.
        """
        with self.database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                query, params=params, param_types=param_types
            )
            for row in results:
                yield list(row)

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
        return list(
            self._execute_query_stream(query, params=params, param_types=param_types)
        )
