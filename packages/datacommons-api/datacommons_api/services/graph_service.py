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

# Standard library imports
import hashlib
import logging

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from datacommons_api.core.constants import DEFAULT_NODE_FETCH_LIMIT
from datacommons_db.models.edge import EdgeModel
from datacommons_db.models.node import NodeModel
from datacommons_schema.models.jsonld import (
    GraphNode,
    GraphNodePropertyValue,
    JSONLDDocument,
)

# Configure logging
logger = logging.getLogger(__name__)


class GraphServiceError(Exception):
    """
    Custom exception for errors in GraphService operations.
    """


# Namespace configuration
BASE_NAMESPACES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}

NAMESPACES = {
    "dc": "https://datacommons.org/browser/",
    "schema": "https://schema.org/",
}

LOCAL_NAMESPACE_NAME = "local"
LOCAL_NAMESPACE_URL = f"http://localhost:5000/schema/{LOCAL_NAMESPACE_NAME}/"

OBSERVATION_TYPES = {"StatVarObservation", "schema:Observation"}


def generate_literal_id(value: str) -> str:
    """
    Generate a deterministic ID for a literal string value.

    Args:
      value: The literal string value

    Returns:
      A deterministic ID string format dcid:l/<md5_hash_of_string>
    """
    hash_obj = hashlib.md5(value.encode("utf-8"))
    return f"dcid:l/{hash_obj.hexdigest()}"


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

    # Helper to extract a string value from a generic property
    def extract_string_value(prop: Any) -> str | None:
        if not prop:
            return None
        if isinstance(prop, list) and prop:
            prop = prop[0]
        if hasattr(prop, "value") and prop.value is not None:
            return str(prop.value)
        return None

    name_val = extract_string_value(getattr(graph_node, "name", None))
    value_val = extract_string_value(getattr(graph_node, "value", None))

    return NodeModel(
        subject_id=graph_node.id,
        name=name_val,
        value=value_val,
        types=types,
    )


def create_edge_model(
    subject_id: str,
    predicate: str,
    object_id: str | None = None,
    provenance: str | None = None,
) -> EdgeModel:
    """
    Create an EdgeModel instance from edge data.

    Args:
      subject_id: The ID of the source node
      predicate: The edge predicate
      object_id: The ID of the generic or literal destination node
      provenance: The ID of a node that is the provenance of the edge
        TODO: Add an example of a provenance node

    Returns:
      An EdgeModel instance
    """
    if not object_id:
        message = f"Missing object_id for edge {subject_id} {predicate}"
        raise GraphServiceError(message)

    # Handle lists of values by creating multiple edges
    edge = EdgeModel(
        object_id=object_id,
        predicate=predicate,
        subject_id=subject_id,
    )
    if provenance:
        edge.provenance = provenance
    return edge


def extract_edges_from_node(graph_node: GraphNode) -> list[EdgeModel | NodeModel]:
    """
    Extract EdgeModel and literal NodeModel instances from a GraphNode's properties.

    Args:
      graph_node: The GraphNode to extract edges from

    Returns:
      A list of EdgeModel and literal NodeModel instances
    """
    models = []

    for predicate, edge_values in graph_node.model_dump().items():
        # Skip node metadata
        if predicate in ["@id", "@type", "id", "type"]:
            continue

        # Handle both single values and lists of values
        values_list = edge_values if isinstance(edge_values, list) else [edge_values]

        for edge_value in values_list:
            # If the edge value is a dictionary, parse it as a GraphNodePropertyValue
            if isinstance(edge_value, dict):
                edge_graph_node = GraphNodePropertyValue.model_validate(edge_value)
                edge = create_edge_model(
                    subject_id=graph_node.id,
                    predicate=predicate,
                    object_id=edge_graph_node.id,
                )
                models.append(edge)
            else:
                str_val = str(edge_value)
                literal_id = generate_literal_id(str_val)
                edge = create_edge_model(
                    subject_id=graph_node.id,
                    predicate=predicate,
                    object_id=literal_id,
                )
                literal_node = NodeModel(
                    subject_id=literal_id,
                    value=str_val
                )
                models.append(edge)
                models.append(literal_node)
    return models


def node_model_to_graph_node(node: NodeModel) -> GraphNode:
    """
    Transform a SQLAlchemy Node into a JSON-LD GraphNode.

    Outgoing edges are transformed into properties where the predicate becomes the property name
    and the value is wrapped in a GraphNodePropertyValue object that includes provenance.

    Args:
      node: The SQLAlchemy Node instance to transform

    Returns:
      A GraphNode representing the transformed node with edge properties
    """
    # Start with the base node properties
    graph_node_properties = {"@id": node.subject_id, "@type": node.types}

    # Group edges by predicate
    edge_groups = {}
    for edge in node.outgoing_edges:
        if edge.predicate not in edge_groups:
            edge_groups[edge.predicate] = []

        property_value = {}
        
        # Check if the target node is a literal node (has a value)
        # We use the relationship `target_node` which is eagerly loaded
        if edge.target_node and edge.target_node.value is not None:
             property_value["@value"] = edge.target_node.value
        # If it's a reference to another node, use the object_id
        else:
            property_value["@id"] = edge.object_id

        if edge.provenance:
            property_value["@provenance"] = edge.provenance

        edge_groups[edge.predicate].append(property_value)

    # Add edge groups to properties
    for predicate, values in edge_groups.items():
        # If there's only one value, don't wrap it in a list
        graph_node_properties[predicate] = values[0] if len(values) == 1 else values

    return GraphNode(**graph_node_properties)


class GraphService:
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
        logger.info("Initialized GraphService with new session")

    def get_graph_nodes(
        self,
        limit: int = DEFAULT_NODE_FETCH_LIMIT,
        type_filter: list[str] | None = None,
    ) -> JSONLDDocument:
        """
        Get nodes with their outgoing edges, and transform them into JSON-LD format.

        Args:
          limit: Maximum number of nodes to return
          type_filter: Optional type filter for nodes

        Returns:
          A JSONLDDocument containing the transformed nodes
        """
        logger.info(
            "Fetching graph nodes (limit=%d, type_filter=%s)", limit, type_filter
        )
        node_models = self._get_nodes_with_outgoing_edges(
            limit=limit, type_filter=type_filter
        )
        graph_nodes = [node_model_to_graph_node(n) for n in node_models]
        logger.info("Transformed %d nodes to JSON-LD format", len(graph_nodes))

        return JSONLDDocument(
            context={
                "@vocab": LOCAL_NAMESPACE_URL,
                LOCAL_NAMESPACE_NAME: LOCAL_NAMESPACE_URL,
                **BASE_NAMESPACES,
            },
            graph=graph_nodes,
        )

    def _get_nodes_with_outgoing_edges(
        self,
        limit: int = DEFAULT_NODE_FETCH_LIMIT,
        type_filter: list[str] | None = None,
    ) -> list[NodeModel]:
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
            logger.info("Filtering nodes by types: %s", type_filter)
            query = query.filter(
                text(
                    "EXISTS ("
                    "  SELECT 1 "
                    "    FROM UNNEST(types) AS t "
                    "   WHERE t IN UNNEST(:type_filter)"
                    ")"
                )
            ).params(type_filter=type_filter)

        # Eagerly load outgoing edges AND their target nodes to avoid N+1 queries
        query = query.options(
            joinedload(NodeModel.outgoing_edges).joinedload(EdgeModel.target_node)
        ).limit(limit)

        nodes = query.all()
        logger.debug("Retrieved %d nodes with outgoing edges", len(nodes))
        return nodes

    def insert_graph_nodes(self, jsonld: JSONLDDocument) -> None:
        """
        Insert nodes and edges from a JSON-LD document into the database.

        Raises an exception if the node already exists.

        This method processes the JSON-LD document, creating NodeModel and EdgeModel
        instances for each node and its edges. It handles both literal values and
        references to other nodes, preserving provenance information.

        Args:
          jsonld: The JSON-LD document containing nodes and edges to insert
        """
        nodes: list[NodeModel] = []
        edges: list[EdgeModel] = []

        logger.info("Inserting %d nodes from JSON-LD document", len(jsonld.graph))

        # Process each node in the graph
        for graph_node in jsonld.graph:
            # Create node model
            node_model = create_node_model(graph_node)
            nodes.append(node_model)

            # Extract and create edge models
            node_edges = extract_edges_from_node(graph_node)
            edges.extend(node_edges)

        logger.info("Inserting %d nodes and %d edges", len(nodes), len(edges))

        # Add all nodes and edges to the session
        self.session.add_all(nodes)
        self.session.add_all(edges)

        # Commit the transaction
        self.session.commit()
        logger.info("Successfully committed all nodes and edges to database")
