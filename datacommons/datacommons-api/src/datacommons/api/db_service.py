from typing import List, Optional
import logging

from sqlalchemy import text
from sqlalchemy.orm import joinedload, Session
from datacommons.db.models import NodeModel, EdgeModel
from datacommons.schema.models.jsonld import GraphNode, JSONLDDocument, EdgeValue

# Configure logging
logger = logging.getLogger(__name__)


class DataCommonsValidationError(Exception):
  """
  Custom exception for validation errors in DataCommons operations.
  """
  pass


# Namespace configuration
BASE_NAMESPACES = {
  'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
  'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
  'xsd': 'http://www.w3.org/2001/XMLSchema#'
}

NAMESPACES = {
  'dc': 'https://datacommons.org/',
  'schema': 'https://schema.org/',
}

LOCAL_NAMESPACE_NAME = "local"
LOCAL_NAMESPACE_URL = f"http://localhost:5000/schema/{LOCAL_NAMESPACE_NAME}/"


def create_node_model(graph_node: GraphNode) -> NodeModel:
  """
  Create a NodeModel instance from a GraphNode.
  
  Args:
    graph_node: The GraphNode to convert
    
  Returns:
    A NodeModel instance
  """
  types = graph_node.type
  if not isinstance(types, list):
    types = [types]
  types = [t for t in types if t is not None]
  
  return NodeModel(
    subject_id=graph_node.id,
    types=types,
  )

def create_edge_model(
  subject_id: str,
  predicate: str,
  object_id: str | None = None,
  object_value: str | None = None,
  provenance: Optional[str] = None
) -> EdgeModel:
  """
  Create an EdgeModel instance from edge data.
  
  Args:
    subject_id: The ID of the source node
    predicate: The edge predicate
    value_data: The edge value
      - A string literal
      - A GraphNode
    provenance: Optional provenance information
    
  Returns:
    An EdgeModel instance
  """
  # Handle lists of values by creating multiple edges
  edge = EdgeModel(
    object_id=object_id,
    predicate=predicate,
    subject_id=subject_id,
  )
  if provenance:
    edge.provenance = provenance
  if object_value:
    edge.object_value = object_value
  if object_value and not object_id:
    # If the edge value is a string, use the subject id as the object id
    edge.object_id = subject_id
  if not object_id and not object_value:
    raise DataCommonsValidationError(
      f"Missing object_id or object_value for edge {subject_id} {predicate}"
    )
  return edge



def extract_edges_from_node(graph_node: GraphNode) -> List[EdgeModel]:
  """
  Extract EdgeModel instances from a GraphNode's properties.
  
  Args:
    graph_node: The GraphNode to extract edges from
    
  Returns:
    A list of EdgeModel instances
  """
  edges = []
  
  for predicate, edge_values in graph_node.model_dump().items():
    # Skip node metadata
    if predicate in ['@id', '@type', 'id', 'type']:
      continue
      
    # Handle both single values and lists of values
    edge_values = edge_values if isinstance(edge_values, list) else [edge_values]
    
    for edge_value in edge_values:
      # If the edge value is a dictionary, parse it as an EdgeValue
      if isinstance(edge_value, dict):
        edge_graph_node = EdgeValue.model_validate(edge_value)
        edge = create_edge_model(
          subject_id=graph_node.id,
          predicate=predicate,
          object_id=edge_graph_node.id,
          object_value=edge_graph_node.value,
        )
      else:
        edge = create_edge_model(
          subject_id=graph_node.id,
          predicate=predicate,
          object_id=graph_node.id, # For literal values, use the node id as the object id
          object_value=edge_value,
        )
      edges.append(edge)
  return edges

def node_model_to_graph_node(node: NodeModel) -> GraphNode:
  """
  Transform a SQLAlchemy Node into a JSON-LD GraphNode.
  
  Outgoing edges are transformed into properties where the predicate becomes the property name
  and the value is wrapped in an EdgeValue object that includes provenance.
  
  Args:
    node: The SQLAlchemy Node instance to transform
    
  Returns:
    A GraphNode representing the transformed node with edge properties
  """
  # Start with the base node properties
  graph_node_properties = {
    '@id': node.subject_id,
    '@type': node.types
  }
  
  # Group edges by predicate
  edge_groups = {}
  for edge in node.outgoing_edges:
    if edge.predicate not in edge_groups:
      edge_groups[edge.predicate] = []
    
    property_value = {}
    # If the edge has a literal value, add it to the property value
    if edge.object_value:
      property_value['@value'] = edge.object_value
    # If the edge has an object id, add it to the property value
    else:
      property_value['@id'] = edge.object_id
    
    # If the edge has provenance, add it to the property value
    if edge.provenance:
      property_value['@provenance'] = edge.provenance
    
    edge_groups[edge.predicate].append(property_value)

  # Add edge groups to properties
  for predicate, values in edge_groups.items():
    # If there's only one value, don't wrap it in a list
    graph_node_properties[predicate] = values[0] if len(values) == 1 else values
  
  return GraphNode(**graph_node_properties)

class DbService:
  """
  Service for managing graph database operations.
  
  This service provides methods for querying and inserting nodes and edges
  in the graph database, with support for JSON-LD format.
  """
  
  def __init__(self, session: Session):
    """
    Initialize the database service.
    
    Args:
      session: SQLAlchemy session for database operations
    """
    self.session = session
    logger.info("Initialized DbService with new session")
  
  def get_graph_nodes(self, limit: int = 100, type_filter: Optional[str] = None) -> JSONLDDocument:
    """
    Get nodes with their outgoing edges, and transform them into JSON-LD format.
    
    Args:
      limit: Maximum number of nodes to return
      type_filter: Optional type filter for nodes
      
    Returns:
      A JSONLDDocument containing the transformed nodes
    """
    logger.info(f"Fetching graph nodes (limit={limit}, type_filter={type_filter})")
    node_models = self._get_nodes_with_outgoing_edges(limit=limit, type_filter=type_filter)
    graph_nodes = [node_model_to_graph_node(n) for n in node_models]
    logger.info(f"Transformed {len(graph_nodes)} nodes to JSON-LD format")
    
    return JSONLDDocument(
      context={
        '@vocab': LOCAL_NAMESPACE_URL,
        LOCAL_NAMESPACE_NAME: LOCAL_NAMESPACE_URL,
        **BASE_NAMESPACES
      },
      graph=graph_nodes
    )

  def _get_nodes_with_outgoing_edges(self, limit: int = 100, type_filter: Optional[str] = None) -> List[NodeModel]:
    """
    Get nodes with their outgoing edges.
    
    Args:
      limit: Maximum number of nodes to return
      type_filter: Optional type filter for nodes
      
    Returns:
      A list of NodeModel instances with their outgoing edges loaded
    """
    query = self.session.query(NodeModel)
    
    if type_filter:
      query = query.filter(text(":v IN UNNEST(types)")).params(v=type_filter)
    
    # Load outgoing edges
    query = query.options(
      joinedload(NodeModel.outgoing_edges)
    ).limit(limit)
    
    nodes = query.all()
    logger.debug(f"Retrieved {len(nodes)} nodes with outgoing edges")
    return nodes

  def insert_graph_nodes(self, jsonld: JSONLDDocument) -> None:
    """
    Insert nodes and edges from a JSON-LD document into the database.
    
    This method processes the JSON-LD document, creating NodeModel and EdgeModel
    instances for each node and its edges. It handles both literal values and
    references to other nodes, preserving provenance information.
    
    Args:
      jsonld: The JSON-LD document containing nodes and edges to insert
    """
    nodes: List[NodeModel] = []
    edges: List[EdgeModel] = []
    
    logger.info(f"Inserting {len(jsonld.graph)} nodes from JSON-LD document")
    
    # Process each node in the graph
    for graph_node in jsonld.graph:
      # Create node model
      node_model = create_node_model(graph_node)
      nodes.append(node_model)
      
      # Extract and create edge models
      node_edges = extract_edges_from_node(graph_node)
      edges.extend(node_edges)
    
    logger.info(f"Inserting {len(nodes)} nodes and {len(edges)} edges")
    
    # Insert nodes first
    self.session.add_all(nodes)
    self.session.flush()  # Flush to get node IDs
    
    # Then insert edges
    self.session.add_all(edges)
    
    # Commit the transaction
    self.session.commit()
    logger.info("Successfully committed all nodes and edges to database")
