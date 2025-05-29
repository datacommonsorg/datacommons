
from typing import Generator
from datacommons.db.session import get_session
from datacommons.api.services.graph_service import GraphService
from datacommons.api.core.config import get_config

def with_graph_service() -> Generator[GraphService, None, None]:
  """
  FastAPI dependency to handle database session creation and cleanup.

  Returns:
    GraphService: A GraphService instance
  """
  config = get_config()
  db = get_session(config.SPANNER_PROJECT_ID, config.SPANNER_INSTANCE_ID, config.SPANNER_DATABASE_NAME)
  graph_service = GraphService(db)
  try:
    yield graph_service
  finally:
    db.close()
