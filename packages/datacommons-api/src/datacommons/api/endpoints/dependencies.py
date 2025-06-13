# Copyright 2025 Google LLC.
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


from collections.abc import Generator

from datacommons.api.core.config import get_config
from datacommons.api.services.graph_service import GraphService
from datacommons.db.session import get_session


def with_graph_service() -> Generator[GraphService, None, None]:
    """
    FastAPI dependency to handle database session creation and cleanup.

    Returns:
      GraphService: A GraphService instance
    """
    config = get_config()
    db = get_session(config.GCP_PROJECT_ID, config.GCP_SPANNER_INSTANCE_ID, config.GCP_SPANNER_DATABASE_NAME)
    graph_service = GraphService(db)
    try:
        yield graph_service
    finally:
        db.close()
