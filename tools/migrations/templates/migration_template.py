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


class Migration(SchemaMigration):
    description: str = "__DESCRIPTION__"
    creation_timestamp: str = "__CREATION_TIMESTAMP__"

    def upgrade(self, spanner_client: SpannerClient) -> None:
        """Executes forward schema changes to upgrade the database.

        Args:
            spanner_client: SpannerClient instance to execute DDL / DML.

        Raises:
            RuntimeError: If any DDL or DML operation fails.
        """
        # Example DDL execution:
        # result = spanner_client.execute_ddl([
        #     "CREATE TABLE ExampleTable (Id STRING(64) NOT NULL) PRIMARY KEY (Id)"
        # ])
        # if result.status != ExecutionStatus.SUCCESS:
        #     raise RuntimeError(f"Failed to apply migration: {result.error_message}")
        raise NotImplementedError(
            "Migration upgrade logic has not been implemented yet."
        )
