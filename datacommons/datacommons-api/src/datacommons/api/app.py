
from typing import Generator
from fastapi import FastAPI, Depends
from datacommons.db.spanner import get_spanner_session
from datacommons.db.schema import JSONLDDocument
from datacommons.db.service import GraphService
from .config import get_config
from .responses import UpdateResponse

# FastAPI initialization
app = FastAPI(
  title="Data Commons API",
  version="0.1.0",
  openapi_url="/openapi.json",
  docs_url="/docs",
  redoc_url="/redoc",
  debug=True
)

def with_graph_service() -> Generator[GraphService, None, None]:
  """
  Decorator to handle database session creation and cleanup.
    
  Returns:
    Result of the function execution
  """
  config = get_config()
  db = get_spanner_session(config.SPANNER_PROJECT_ID, config.SPANNER_INSTANCE_ID, config.SPANNER_DATABASE_NAME)
  graph_service = GraphService(db)
  try:
    yield graph_service
  finally:
    db.close()

# JSON-LD endpoint
@app.get("/nodes/", response_model=JSONLDDocument)
def get_nodes(
  limit: int = 100,
  type: str = None,
  graph_service: GraphService = Depends(with_graph_service)
) -> JSONLDDocument:
  """
  Get nodes with their edges
  """
  # Get nodes with their edges
  response_document = graph_service.get_graph_nodes(limit=limit, type_filter=type)
  return response_document

@app.post("/nodes/")
def insert_nodes(
  jsonld: JSONLDDocument,
  graph_service: GraphService = Depends(with_graph_service)
) -> UpdateResponse:
  """Insert a JSON-LD document into the database"""
  try:
    graph_service.insert_graph_nodes(jsonld)
    return UpdateResponse(success=True, message=f"Inserted {len(jsonld.graph)} nodes successfully")
  except Exception as e:
    return UpdateResponse(success=False, message=str(e))


@app.get("/test/")
def test(
  graph_service: GraphService = Depends(with_graph_service)
):
  """Test endpoint to fetch raw nodes"""
  config = get_config()
  db = get_spanner_session(config.SPANNER_PROJECT_ID, config.SPANNER_INSTANCE_ID, config.SPANNER_DATABASE_NAME)
  try:
    from datacommons.db.models import NodeModel
    print("Fetching nodes...")
    nodes = db.query(NodeModel).all()
    print("Nodes fetched:", len(nodes))
    # Convert nodes to dict for serialization
    return [{
      "subject_id": node.subject_id,
      "name": node.name,
      "types": node.types
    } for node in nodes]
  finally:
    db.close()


