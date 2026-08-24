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

from typing import Any

from google.cloud import spanner


class SpannerClient:
    """Helper client for querying and asserting Cloud Spanner tables."""

    def __init__(self, project_id: str, instance_id: str, database_id: str):
        self.project_id = project_id
        self.instance_id = instance_id
        self.database_id = database_id
        self._client: spanner.Client | None = None
        self._database = None

    def _get_db(self):
        if self._database is None:
            self._client = spanner.Client(project=self.project_id)
            instance = self._client.instance(self.instance_id)
            self._database = instance.database(self.database_id)
        return self._database

    def query(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Executes a SQL read query on the Spanner database."""
        db = self._get_db()
        with db.snapshot() as snapshot:
            results = snapshot.execute_sql(sql, params=params)
            rows = []
            for row in results:
                # Map column names to values
                row_dict = {}
                for field, val in zip(results.fields, row, strict=False):
                    row_dict[field.name] = val
                rows.append(row_dict)
            return rows

    def count_observations(self, variable: str | None = None) -> int:
        """Counts total observation rows in the Observation table."""
        try:
            if variable:
                sql = "SELECT COUNT(*) as cnt FROM Observation WHERE variable_measured = @var"
                rows = self.query(sql, params={"var": variable})
            else:
                sql = "SELECT COUNT(*) as cnt FROM Observation"
                rows = self.query(sql)
            return rows[0]["cnt"] if rows else 0
        except Exception:
            return 0

    def get_subject_edges(
        self, subject_prefix: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Fetches Edge records starting with a given subject prefix."""
        sql = "SELECT subject_id, predicate, object_id, provenance FROM Edge WHERE subject_id LIKE @pfx LIMIT @lim"
        return self.query(sql, params={"pfx": f"{subject_prefix}%", "lim": limit})

    def get_node(self, subject_id: str) -> dict[str, Any] | None:
        """Fetches a Node record by subject_id."""
        sql = "SELECT subject_id, name, value, types FROM Node WHERE subject_id = @sid LIMIT 1"
        rows = self.query(sql, params={"sid": subject_id})
        return rows[0] if rows else None

    def get_ingestion_history(
        self, workflow_execution_id: str
    ) -> dict[str, Any] | None:
        """Fetches the IngestionHistory record matching a WorkflowExecutionID."""
        try:
            sql = (
                "SELECT WorkflowExecutionID, Status, CompletionTimestamp, IngestedImports "
                "FROM IngestionHistory WHERE WorkflowExecutionID = @wid LIMIT 1"
            )
            rows = self.query(sql, params={"wid": workflow_execution_id})
            return rows[0] if rows else None
        except Exception:
            return None
