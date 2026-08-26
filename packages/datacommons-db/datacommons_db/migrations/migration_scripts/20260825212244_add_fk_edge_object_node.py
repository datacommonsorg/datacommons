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

_ADD_FK_EDGE_OBJECT_NODE_DDL = """
ALTER TABLE Edge
ADD CONSTRAINT FK_Edge_Object_Node
FOREIGN KEY (object_id) REFERENCES Node (subject_id) NOT ENFORCED
""".strip()


class Migration(SchemaMigration):
    description: str = "Add non-enforced foreign key FK_Edge_Object_Node on Edge.object_id referencing Node.subject_id"
    creation_timestamp: str = "2026-08-25T21:22:44Z"

    def upgrade(self, spanner_client: SpannerClient) -> None:
        """Executes forward schema changes to add the non-enforced foreign key constraint.

        Args:
            spanner_client: SpannerClient instance to execute DDL / DML.

        Raises:
            RuntimeError: If any DDL or DML operation fails.
        """
        result = spanner_client.execute_ddl([_ADD_FK_EDGE_OBJECT_NODE_DDL])
        if result.status != ExecutionStatus.SUCCESS:
            raise RuntimeError(
                f"Failed to add FK_Edge_Object_Node constraint to Edge table: {result.error_message}"
            )
