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
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from google.auth.credentials import Credentials
from google.cloud import spanner
from google.cloud.spanner_v1.transaction import Transaction

from datacommons_db.utils.sql_utils import (
    parse_sql_to_statements,
    render_schema_template,
)
from datacommons_db.utils.validators import (
    validate_resource_id,
    validate_table_name,
)


class ExecutionStatus(StrEnum):
    """Status of a Spanner database operation."""

    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


@dataclass(frozen=True)
class DdlResult:
    """Result of a DDL statement execution.

    Attributes:
        status: Execution status enum (SUCCESS or ERROR).
        error_message: Error message string if execution failed, None otherwise.
    """

    status: ExecutionStatus
    error_message: str | None = None


@dataclass(frozen=True)
class DmlResult:
    """Result of a DML statement execution inside a read-write transaction.

    Attributes:
        status: Execution status enum (SUCCESS or ERROR).
        rows_affected: Number of rows modified by the DML statement (0 on failure).
        error_message: Error message string if execution failed, None otherwise.
    """

    status: ExecutionStatus
    rows_affected: int = 0
    error_message: str | None = None


@dataclass(frozen=True)
class QueryResult:
    """Result of a snapshot read query.

    Attributes:
        status: Execution status enum (SUCCESS or ERROR).
        rows: List of rows where each row is a list of column values ([] on failure).
        error_message: Error message string if execution failed, None otherwise.
    """

    status: ExecutionStatus
    rows: list[list[Any]] = field(default_factory=list)
    error_message: str | None = None


class SpannerClient:
    """Client for Cloud Spanner operations, DDL execution, and query execution."""

    def __init__(
        self,
        project_id: str,
        instance_id: str,
        database_id: str,
        credentials: Credentials | None = None,
        *,
        disable_builtin_metrics: bool = True,
    ) -> None:
        """Initialize the SpannerClient.

        Args:
            project_id: GCP project ID.
            instance_id: Cloud Spanner instance ID.
            database_id: Cloud Spanner database ID.
            credentials: Optional Google Cloud credentials object.
            disable_builtin_metrics: Whether to disable built-in Cloud Monitoring metrics export.
        """
        validate_resource_id("project_id", project_id)
        validate_resource_id("instance_id", instance_id)
        validate_resource_id("database_id", database_id)

        self.project_id = project_id
        self.instance_id = instance_id
        self.database_id = database_id

        self.client = spanner.Client(
            project=project_id,
            credentials=credentials,
            disable_builtin_metrics=disable_builtin_metrics,
        )
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

        result = self.execute_query(query, params=params, param_types=param_types)
        return bool(result.status == ExecutionStatus.SUCCESS and result.rows)

    def execute_ddl(self, ddl_statements: list[str]) -> DdlResult:
        """Execute DDL statements and wait for completion.

        Handles operations like CREATE TABLE, ALTER TABLE, etc.

        Args:
            ddl_statements: A non-empty list of DDL statement strings.

        Returns:
            DdlResult with execution status and optional error message.
        """
        if not ddl_statements or not isinstance(ddl_statements, list):
            return DdlResult(
                status=ExecutionStatus.ERROR,
                error_message="ddl_statements must be a non-empty list of str.",
            )

        try:
            operation = self.database.update_ddl(ddl_statements)
            operation.result()
            return DdlResult(status=ExecutionStatus.SUCCESS)
        except Exception as e:  # noqa: BLE001 - must catch all exceptions to ensure a DdlResult is always returned
            return DdlResult(status=ExecutionStatus.ERROR, error_message=str(e))

    def execute_dml(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        param_types: dict[str, Any] | None = None,
    ) -> DmlResult:
        """Execute a DML statement inside a Spanner read-write transaction.

        Handles operations like INSERT, UPDATE, DELETE

        Args:
            query: The parameterized DML statement.
            params: Dictionary of parameters.
            param_types: Dictionary of parameter types.

        Returns:
            DmlResult with execution status, rows affected, and optional error message.
        """

        def _unit_of_work(transaction: Transaction) -> int:
            return transaction.execute_update(
                query, params=params, param_types=param_types
            )

        try:
            rows_affected = self.database.run_in_transaction(_unit_of_work)
            return DmlResult(
                status=ExecutionStatus.SUCCESS, rows_affected=rows_affected
            )
        except Exception as e:  # noqa: BLE001 - must catch all exceptions to ensure a DmlResult is always returned
            return DmlResult(
                status=ExecutionStatus.ERROR,
                rows_affected=0,
                error_message=str(e),
            )

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
    ) -> QueryResult:
        """Execute a read query within a snapshot transaction.

        Handles operations like SELECT.

        Args:
            query: The parameterized SQL query.
            params: Dictionary of parameters.
            param_types: Dictionary of parameter types.

        Returns:
            QueryResult with execution status, rows, and optional error message.
        """
        try:
            rows = list(
                self._execute_query_stream(
                    query, params=params, param_types=param_types
                )
            )
            return QueryResult(status=ExecutionStatus.SUCCESS, rows=rows)
        except Exception as e:  # noqa: BLE001 - must catch all exceptions to ensure a QueryResult is always returned
            return QueryResult(
                status=ExecutionStatus.ERROR, rows=[], error_message=str(e)
            )

    def initialize_database(
        self,
        schema_path: Path | str | None = None,
        *,
        embedding_table: str = "NodeEmbedding",
        embedding_index: str = "NodeEmbeddingIndex",
        embedding_label_index: str = "NodeEmbeddingLabelIndex",
        embedding_space: int = 768,
        models: list[dict[str, str]] | None = None,
        location: str | None = None,
    ) -> DdlResult:
        """Initializes the database by executing all base schema DDL statements.

        Resolves template placeholders in the baseline schema file (or custom schema path)
        and applies the DDL statements to Cloud Spanner.

        Args:
            schema_path: Path to the schema SQL file. If None, uses the bundled schema.sql.
            embedding_table: Name of the vector embedding table. Defaults to 'NodeEmbedding'.
            embedding_index: Name of the vector search index. Defaults to 'NodeEmbeddingIndex'.
            embedding_label_index: Name of the secondary index on embedding label. Defaults to 'NodeEmbeddingLabelIndex'.
            embedding_space: Dimensionality of embedding vectors. Defaults to 768.
            models: List of model dictionaries with 'name' and 'endpoint'. Defaults to text-embedding-005.
            location: GCP region for model endpoints. Defaults to 'us-central1'.

        Returns:
            DdlResult indicating execution status.
        """
        if schema_path is None:
            resolved_schema_path = (
                Path(__file__).parent.parent / "schema" / "schema.sql"
            )
        else:
            resolved_schema_path = Path(schema_path)

        if not resolved_schema_path.exists():
            return DdlResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Schema file not found at '{resolved_schema_path}'",
            )

        template_content = resolved_schema_path.read_text(encoding="utf-8")
        rendered_sql = render_schema_template(
            template_content,
            project_id=self.project_id,
            location=location or "us-central1",
            embedding_table=embedding_table,
            embedding_index=embedding_index,
            embedding_label_index=embedding_label_index,
            embedding_space=embedding_space,
            models=models,
        )
        statements = parse_sql_to_statements(rendered_sql)
        return self.execute_ddl(statements)

    def acquire_lock(
        self,
        workflow_id: str,
        timeout: int = 300,
        lock_id: str = "global_ingestion_lock",
    ) -> bool:
        """Attempts to acquire the global ingestion lock directly in Spanner.

        Args:
            workflow_id: The ID of the workflow or process attempting to acquire the lock.
            timeout: Maximum duration in seconds after which a held lock is considered stale.
            lock_id: Identifier of the lock row in IngestionLock. Defaults to 'global_ingestion_lock'.

        Returns:
            True if the lock was acquired, False if currently held by an active owner.

        Raises:
            Exception: If database transaction execution fails.
        """

        def _acquire(transaction: Transaction) -> bool:
            sql = "SELECT LockOwner, AcquiredTimestamp FROM IngestionLock WHERE LockID = @lockId"
            params = {"lockId": lock_id}
            param_types = {"lockId": spanner.param_types.STRING}

            row_found = False
            current_owner = None
            acquired_at = None

            results = transaction.execute_sql(
                sql, params=params, param_types=param_types
            )
            for row in results:
                row_found = True
                current_owner, acquired_at = row[0], row[1]

            lock_is_available = False
            if not row_found or current_owner is None:
                lock_is_available = True
            elif acquired_at is not None:
                now_utc = datetime.now(UTC)
                if isinstance(acquired_at, datetime):
                    acquired_dt = (
                        acquired_at
                        if acquired_at.tzinfo
                        else acquired_at.replace(tzinfo=UTC)
                    )
                    elapsed = (now_utc - acquired_dt).total_seconds()
                    if elapsed > timeout:
                        lock_is_available = True

            if lock_is_available:
                if not row_found:
                    sql_statement = """
                        INSERT INTO IngestionLock (LockID, LockOwner, AcquiredTimestamp)
                        VALUES (@lockId, @workflowId, PENDING_COMMIT_TIMESTAMP())
                    """
                else:
                    sql_statement = """
                        UPDATE IngestionLock
                        SET LockOwner = @workflowId, AcquiredTimestamp = PENDING_COMMIT_TIMESTAMP()
                        WHERE LockID = @lockId
                    """
                transaction.execute_update(
                    sql_statement,
                    params={"workflowId": workflow_id, "lockId": lock_id},
                    param_types={
                        "workflowId": spanner.param_types.STRING,
                        "lockId": spanner.param_types.STRING,
                    },
                )
                return True
            return False

        return self.database.run_in_transaction(_acquire)

    def release_lock(
        self,
        workflow_id: str,
        lock_id: str = "global_ingestion_lock",
    ) -> bool:
        """Releases the global lock if currently owned by the specified workflow_id.

        Args:
            workflow_id: The ID of the workflow or process attempting to release the lock.
            lock_id: Identifier of the lock row in IngestionLock. Defaults to 'global_ingestion_lock'.

        Returns:
            True if the lock was owned and successfully released, False otherwise.

        Raises:
            Exception: If database transaction execution fails.
        """

        def _release(transaction: Transaction) -> bool:
            sql = "SELECT LockOwner, AcquiredTimestamp FROM IngestionLock WHERE LockID = @lockId"
            params = {"lockId": lock_id}
            param_types = {"lockId": spanner.param_types.STRING}

            current_owner = None
            results = transaction.execute_sql(
                sql, params=params, param_types=param_types
            )
            for row in results:
                current_owner = row[0]

            if current_owner and current_owner == workflow_id:
                sql_update = """
                    UPDATE IngestionLock
                    SET LockOwner = NULL, AcquiredTimestamp = NULL
                    WHERE LockID = @lockId
                """
                transaction.execute_update(
                    sql_update,
                    params={"lockId": lock_id},
                    param_types={"lockId": spanner.param_types.STRING},
                )
                return True
            return False

        return self.database.run_in_transaction(_release)
