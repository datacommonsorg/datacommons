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

_CREATE_SCHEMA_VERSION_TABLE_DDL = """
CREATE TABLE SchemaVersion (
    SchemaVersionId UUID NOT NULL DEFAULT (NEW_UUID()),
    CreationTimestamp STRING(64) NOT NULL,
    AppliedTimestamp TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
    Description STRING(MAX) NOT NULL
) PRIMARY KEY (SchemaVersionId)
""".strip()


class Migration(SchemaMigration):
    """Bootstrap migration for initial schema setup and SchemaVersion table initialization."""

    description: str = "Add SchemaVersion table to bootstrap schema versioning."
    creation_timestamp: str = "2026-08-17T00:00:00Z"

    def upgrade(self, spanner_client: SpannerClient) -> None:
        """Executes forward schema changes to initialize SchemaVersion table.

        Args:
            spanner_client: SpannerClient instance to execute DDL / DML.

        Raises:
            RuntimeError: If DDL operation fails.
        """
        if not spanner_client.table_exists("SchemaVersion"):
            result = spanner_client.execute_ddl([_CREATE_SCHEMA_VERSION_TABLE_DDL])
            if result.status != ExecutionStatus.SUCCESS:
                raise RuntimeError(
                    f"Failed to create SchemaVersion table: {result.error_message}"
                )
