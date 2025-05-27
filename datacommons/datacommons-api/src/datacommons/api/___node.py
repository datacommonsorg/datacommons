from flask import request
from flask_restx import Resource, fields, Namespace, reqparse
# from flask_jwt_extended import jwt_required
# from .models import Triple, Observation
# from .storage import Storage
from datacommons.api.app import api
from datacommons.db.service import get_nodes_with_edges
from typing import Dict, List, Union, TypedDict, Optional
from datacommons.db.models import NodeModel, EdgeModel
from datacommons.schema.models.jsonld import JsonLdDocument

# API namespaces
nodes_ns = Namespace('nodes', description='Nodes operations')

# Register namespaces
api.add_namespace(nodes_ns)

# TODO: Keep this namespace in mind: https://schema.org/version/latest/schemaorg-current-https.jsonld
# For DC: StatisticalVariable, StatVarPeerGroup, Observation, Topic, 
# Other: Provenance
# Deprecated: StatVarGroup

# Edge model for Swagger
edge_model = api.model('Edge', {
    'predicate': fields.String(required=True, description='The relationship type'),
    'object_id': fields.String(required=True, description='The target node ID'),
    'object_value': fields.String(required=False, description='The literal value if present'),
    'provenance': fields.String(required=True, description='Source of the edge data')
})

# Node model for Swagger
node_model = api.model('GraphNode', {
    '@id': fields.String(required=True, description='The node identifier', example='local:Person'),
    'name': fields.String(required=False, description='Human-readable name of the node', example='John Doe'),
    'types': fields.List(fields.String, required=False, description='List of node types', example=['local:Person']),
    'outgoing': fields.Wildcard(fields.Raw, description='Allows any other arbitrary properties', example={})
})

# Response model for the API
jsonld_document_model = api.model('GraphResponse', {
    '@context': fields.Raw(required=True, description='JSON-LD context information', example={
        '@vocab': 'http://localhost:5000/schema/local/',
        'local': 'http://localhost:5000/schema/local/',
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
        'xsd': 'http://www.w3.org/2001/XMLSchema#',
        'outgoing': '@nest'
    }),
    '@graph': fields.List(fields.Nested(node_model), description='List of graph nodes')
})

create_node_response_model = api.model('CreateNodeResponse', {
    'success': fields.Boolean(required=True, description='Whether the node was created successfully')
})

# Constants
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

class EdgeValue(TypedDict):
    predicate: str
    object_id: Optional[str]
    object_value: Optional[str]
    provenance: str

class TransformedNode(TypedDict):
    id: str  # Using id instead of @id since @ is not valid in Python type annotations
    name: Optional[str]
    types: Optional[List[str]]
    # Dynamic properties will be added based on predicates

def transform_node_to_api_format(node: NodeModel) -> Dict[str, Union[str, List[str], Dict[str, str]]]:
    """
    Transform a SQLAlchemy Node with its edges into the API format.
    Outgoing edges are flattened into properties where the predicate becomes the property name
    and the value is either the object_id (prefixed with appropriate namespace) or object_value.
    
    Args:
        node: The SQLAlchemy Node instance to transform
        
    Returns:
        A dictionary representing the transformed node with flattened edge properties
    """
    # Start with the base node properties
    transformed: Dict[str, Union[str, List[str], Dict[str, str]]] = {
        '@id': get_namespaced_id(node.subject_id),
        'name': node.name,
        'types': node.types,
        'outgoing': {}
    }
    
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

@nodes_ns.route('/')
class NodesAPI(Resource):
    @nodes_ns.doc('get_nodes')
    @nodes_ns.marshal_with(jsonld_document_model)
    def get(self):
        """Get the entire graph"""
        # Get query parameters
        parser = reqparse.RequestParser()
        parser.add_argument('limit', type=int, default=100, help='Maximum number of nodes to return')
        parser.add_argument('type', type=str, help='Filter nodes by type')
        args = parser.parse_args()
        
        # Get nodes with their edges
        nodes = get_nodes_with_edges(limit=args['limit'], type_filter=args['type'])
        
        # Transform nodes to API format
        transformed_nodes = [transform_node_to_api_format(node) for node in nodes]
        
        return {
            '@context': {
                '@vocab': LOCAL_NAMESPACE_URL,
                LOCAL_NAMESPACE_NAME: LOCAL_NAMESPACE_URL,
                **BASE_NAMESPACES,
                'outgoing': "@nest"
            },
            '@graph': transformed_nodes
        }
    
    @nodes_ns.doc('post_nodes')
    @nodes_ns.expect(jsonld_document_model)
    @nodes_ns.marshal_with(create_node_response_model)
    def post(self):
        """Create a new node"""
        # Parse JSON-LD request body
        data = request.json
        print(data)

        jsonld_doc = JsonLdDocument.from_json(data)

        print(jsonld_doc)

        # Validate request body
        return {
            "success": True
        }
