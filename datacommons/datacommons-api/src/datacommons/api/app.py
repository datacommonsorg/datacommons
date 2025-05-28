
from typing import Generator
import traceback
from fastapi import FastAPI, Depends
from datacommons.db.spanner import get_spanner_session
from datacommons.schema.models.jsonld import JSONLDDocument
from .db_service import DbService
from .config import get_config
from .responses import UpdateResponse
from .logging import get_logger

logger = get_logger(__name__)

# FastAPI initialization
app = FastAPI(
  title="Data Commons API",
  version="0.1.0",
  openapi_url="/openapi.json",
  docs_url="/docs",
  redoc_url="/redoc",
  debug=True
)

def with_graph_service() -> Generator[DbService, None, None]:
  """
  Decorator to handle database session creation and cleanup.
    
  Returns:
    Result of the function execution
  """
  config = get_config()
  db = get_spanner_session(config.SPANNER_PROJECT_ID, config.SPANNER_INSTANCE_ID, config.SPANNER_DATABASE_NAME)
  graph_service = DbService(db)
  try:
    yield graph_service
  finally:
    db.close()

# JSON-LD endpoint
@app.get("/nodes/", response_model=JSONLDDocument, response_model_exclude_none=True)
def get_nodes(
  limit: int = 100,
  type: str = None,
  graph_service: DbService = Depends(with_graph_service)
) -> JSONLDDocument:
  """
  Get nodes with their edges
  """
  # Get nodes with their edges
  response_document = graph_service.get_graph_nodes(limit=limit, type_filter=type)
  return response_document

@app.post("/nodes/", response_model=UpdateResponse, response_model_exclude_none=True)
def insert_nodes(
  jsonld: JSONLDDocument,
  graph_service: DbService = Depends(with_graph_service)
) -> UpdateResponse:
  """Insert a JSON-LD document into the database"""
  try:
    graph_service.insert_graph_nodes(jsonld)
    return UpdateResponse(success=True, message=f"Inserted {len(jsonld.graph)} nodes successfully")
  except Exception as e:
    logger.error(f"Error inserting nodes: {e}\n{traceback.format_exc()}")
    return UpdateResponse(success=False, message=str(e))

