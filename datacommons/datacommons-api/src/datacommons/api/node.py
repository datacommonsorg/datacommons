from flask import request
from flask_restx import Resource, fields, Namespace, reqparse
# from flask_jwt_extended import jwt_required
# from .models import Triple, Observation
# from .storage import Storage
from datacommons.api.app import api
from datacommons.db.service import get_nodes_with_edges
from typing import Dict, List, Union, TypedDict, Optional
from datacommons.db.models import Node, Edge

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
    '@id': fields.String(required=True, description='The node identifier'),
    'name': fields.String(required=False, description='Human-readable name of the node'),
    'types': fields.List(fields.String, required=False, description='List of node types'),
    'outgoing': fields.Wildcard(fields.Raw, description='Allows any other arbitrary properties'),
    #'outgoing_edges': fields.List(fields.Nested(edge_model), description='List of outgoing edges')

})

# Response model for the API
node_response_model = api.model('GraphResponse', {
    '@context': fields.Raw(required=True, description='JSON-LD context information'),
    '@graph': fields.List(fields.Nested(node_model), description='List of graph nodes')
})

# Constants
NAMESPACES = {
    'dc': 'https://datacommons.org/',
    'schema': 'https://schema.org/',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'xsd': 'http://www.w3.org/2001/XMLSchema#'
}

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

def transform_node_to_api_format(node: Node) -> Dict[str, Union[str, List[str], Dict[str, str]]]:
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
    @nodes_ns.marshal_with(node_response_model)
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
                # '@vocab': 'https://schema.org/',
                NAMESPACES['dc']: NAMESPACES['dc'],
                NAMESPACES['schema']: NAMESPACES['schema']
            },
            '@graph': transformed_nodes
        }
