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

from datacommons_db.clients.spanner_client import ExecutionStatus, SpannerClient
from datacommons_db.migrations.base import SchemaMigration

_CREATE_LINKED_EDGE_TABLE_DDL = """
CREATE TABLE LinkedEdge (
  predicate STRING(1024) NOT NULL,
  ancestor STRING(1024) NOT NULL,
  child_type STRING(1024) NOT NULL,
  child STRING(1024) NOT NULL,
  provenance STRING(1024) NOT NULL
) PRIMARY KEY(predicate, ancestor, child_type, child, provenance)
""".strip()


class Migration(SchemaMigration):
    description: str = "Add LinkedEdge table"
    creation_timestamp: str = "2026-09-14T19:53:25Z"

    def upgrade(self, spanner_client: SpannerClient) -> None:
        """Executes forward schema changes to upgrade the database.

        Args:
            spanner_client: SpannerClient instance to execute DDL / DML.

        Raises:
            RuntimeError: If any DDL or DML operation fails.
        """
        if spanner_client.table_exists("LinkedEdge"):
            raise RuntimeError("Table 'LinkedEdge' already exists.")

        result = spanner_client.execute_ddl([_CREATE_LINKED_EDGE_TABLE_DDL])
        if result.status != ExecutionStatus.SUCCESS:
            raise RuntimeError(
                f"Failed to create LinkedEdge table: {result.error_message}"
            )
