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

from datacommons_db.clients import ExecutionStatus, SpannerClient
from datacommons_db.migrations.base import SchemaMigration

_CREATE_NODE_EMBEDDING_MODEL_DDL = """
CREATE OR REPLACE MODEL NodeEmbeddingModel
INPUT(
  content STRING(MAX),
  task_type STRING(MAX),
)
OUTPUT(
  embeddings
    STRUCT<
      statistics STRUCT<truncated BOOL, token_count FLOAT64>,
      values ARRAY<FLOAT64>>
)
REMOTE OPTIONS (
  endpoint = '//aiplatform.googleapis.com/projects/{project_id}/locations/{region}/publishers/google/models/text-embedding-005'
)
""".strip()


class Migration(SchemaMigration):
    description: str = "Create remote Vertex AI NodeEmbeddingModel for text embeddings"
    creation_timestamp: str = "2026-09-01T00:00:00Z"
    emulator_supported: bool = False

    def upgrade(self, spanner_client: SpannerClient) -> None:
        """Executes forward schema changes to create NodeEmbeddingModel remote model.

        Args:
            spanner_client: SpannerClient instance to execute DDL / DML.

        Raises:
            RuntimeError: If any DDL operation fails.
        """
        ddl = _CREATE_NODE_EMBEDDING_MODEL_DDL.format(
            project_id=spanner_client.project_id,
            region=spanner_client.region,
        )
        result = spanner_client.execute_ddl([ddl])
        if result.status != ExecutionStatus.SUCCESS:
            raise RuntimeError(
                f"Failed to create NodeEmbeddingModel: {result.error_message}"
            )
