from typing import List
from sqlalchemy import text
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session
from .models import NodeModel, EdgeModel
from .schema import GraphNode, JSONLDDocument


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




def get_namespaced_id(object_id: str) -> str:
  """
  Convert an object_id into a namespaced URI.
  If the object_id already contains a namespace prefix (e.g., 'dc:'), use that.
  Otherwise, try to determine the appropriate namespace based on the object_id pattern.
  
  Args:
      object_id: The object ID to namespace
      
  Returns:
      A namespaced URI string
  """
  # If it already has a namespace prefix, return as is
  if ':' in object_id:
    return object_id

  # Try to determine namespace based on object_id pattern
  if object_id.startswith('dc/'):
    return f"dc:{object_id[3:]}"
  elif object_id.startswith('schema/'):
    return f"schema:{object_id[7:]}"
  # Add more patterns as needed
  
  # Default to dc: namespace if no pattern matches
  return f"dc:{object_id}"

def node_model_to_graph_node(node: NodeModel) -> GraphNode:
  """
  Transform a SQLAlchemy Node into a JSON-LD GraphNode.
  Outgoing edges are flattened into properties where the predicate becomes the property name
  and the value is either the object_id (prefixed with appropriate namespace) or object_value.
  
  Args:
      node: The SQLAlchemy Node instance to transform
      
  Returns:
      A dictionary representing the transformed node with flattened edge properties
  """
  # Start with the base node properties
  print(f"@@ Transforming node {node.subject_id}, node.types: {node.types}, type: {type(node.types)}")
  print(f"@@ get_namespaced_id(node.subject_id)= {get_namespaced_id(node.subject_id)}")
  transformed: GraphNode = GraphNode(
    id=get_namespaced_id(node.subject_id),
    #name=node.name,
    #type=node.types,
    type=node.types,
    #outgoing={}
  )
  print(f"@@ Transformed node {node.subject_id}")

  
  # Flatten outgoing edges into properties
  for edge in node.outgoing_edges:
    # Use predicate as the property name
    property_name = edge.predicate
    
    # Initialize property as list if it doesn't exist
    if property_name not in transformed['outgoing']:
      transformed['outgoing'][property_name] = []
        
    # Create value object with provenance
    value_obj = {
      'provenance': edge.provenance
    }
    
    # Determine the value based on what's available
    if edge.object_value:
      # If we have an object_value, use it directly
      value_obj['value'] = edge.object_value
    elif edge.object_id:
      # If we have an object_id, use it with the appropriate namespace
      value_obj['value'] = get_namespaced_id(edge.object_id)
        
    # Add the value object to the property's list
    transformed['outgoing'][property_name].append(value_obj)
  
  return transformed

class GraphService:
  def __init__(self, session: Session):
    self.session = session
  
  def get_graph_nodes(self, limit=100, type_filter=None) -> JSONLDDocument:
    """
    Get nodes with both incoming and outgoing edges, and transform them into JSONL-LD format.
    """
    node_models = self.get_nodes_with_outgoing_edges(limit=limit, type_filter=type_filter)
    graph_nodes = [node_model_to_graph_node(n) for n in node_models]
    return {
      '@context': {
        '@vocab': LOCAL_NAMESPACE_URL,
        LOCAL_NAMESPACE_NAME: LOCAL_NAMESPACE_URL,
        **BASE_NAMESPACES,
        'outgoing': "@nest"
      },
      '@graph': graph_nodes
    }

  def get_nodes_with_outgoing_edges(self, limit=100, type_filter=None) -> List[NodeModel]:
    """Get nodes with both incoming and outgoing edges."""
    query = self.session.query(NodeModel)
    
    if type_filter:
      query = query.filter(text(":v IN UNNEST(types)")).params(v=type_filter)
    
    # Load both incoming and outgoing edges
    query = query.options(
      joinedload(NodeModel.outgoing_edges),
      #joinedload(Node.incoming_edges)
    ).limit(limit)
    
    nodes = query.all()
    return nodes

  def insert_graph_nodes(self, jsonld: JSONLDDocument):
    """
    Insert nodes and edges from a JSON-LD document into the database.
    """
    # Read all GraphNodes from the JSON-LD document, extracting Node and Edge information
    nodes: List[NodeModel] = []
    edges: List[EdgeModel] = []
    print("Inserting nodes from JSON-LD document")
    for graph_node in jsonld.graph:
      # Extract Node information
      print(f"Inserting node {graph_node.id}")
      types = graph_node.type
      if not isinstance(types, list):
        types = [types]
      else:
        types = [t for t in types if t is not None]
      node_model = NodeModel(
        subject_id=graph_node.id,
        types=types,
      )
      nodes.append(node_model)
    print(f"Inserting {len(nodes)} nodes")
    self.session.add_all(nodes)
    # Commit the transaction
    self.session.commit()
    print("Session committed")
