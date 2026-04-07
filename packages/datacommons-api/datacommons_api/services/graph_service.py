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
import base64
import logging
import traceback
from google.cloud import spanner
from google.cloud.spanner_v1 import database
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from datacommons_api.core.config import get_config
from datacommons_api.core.constants import DEFAULT_NODE_FETCH_LIMIT
from datacommons_db.models.edge import EdgeModel, EDGE_TABLE_NAME
from datacommons_db.models.node import NodeModel, NODE_TABLE_NAME
from datacommons_db.models.edge import OBJECT_VALUE_MAX_LENGTH
from datacommons_schema.models.jsonld import (
    GraphNode,
    GraphNodePropertyValue,
    JSONLDDocument,
)

# Configure logging
logger = logging.getLogger(__name__)

# Silence OpenTelemetry warnings/errors (Spanner client integration triggers these)
logging.getLogger("opentelemetry.metrics._internal").setLevel(logging.ERROR)
logging.getLogger("opentelemetry.sdk.metrics._internal.export").setLevel(
    logging.CRITICAL
)


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
    "dc": "https://datacommons.org/",
    "schema": "https://schema.org/",
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

    # Remove all CURIE namespaces before storing the node id
    subject_id = strip_namespace(graph_node.id)
    types = [strip_namespace(t) for t in types]
    return NodeModel(
        subject_id=subject_id,
        types=types,
    )


def strip_namespace(id: str) -> str:
    """
    Strip all CURIE namespaces from an id.
    """
    return id.split(":")[-1]


def create_edge_model(
    subject_id: str,
    predicate: str,
    object_id: str | None = None,
    object_value: str | None = None,
    provenance: str | None = None,
) -> EdgeModel:
    """
    Create an EdgeModel instance from edge data.

    Args:
      subject_id: The ID of the source node
      predicate: The edge predicate
      object_id: The ID of the target node
      object_value: The edge value
        - A string literal
        - A GraphNode
      provenance: The ID of a node that is the provenance of the edge
        TODO: Add an example of a provenance node

    Returns:
      An EdgeModel instance
    """
    # Handle lists of values by creating multiple edges
    edge = EdgeModel(
        object_id=strip_namespace(object_id),
        predicate=strip_namespace(predicate),
        subject_id=strip_namespace(subject_id),
    )
    if provenance:
        edge.provenance = strip_namespace(provenance)
    if object_value:
        edge.object_value = strip_namespace(object_value) if object_id else object_value
    if object_value and not object_id:
        # If the edge value is a string, use the subject id as the object id
        edge.object_id = strip_namespace(subject_id)
    if not object_id and not object_value:
        message = f"Missing object_id or object_value for edge {subject_id} {predicate}"
        raise GraphServiceError(message)
    return edge


def extract_edges_from_node(graph_node: GraphNode) -> list[EdgeModel]:
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
                    object_value=edge_graph_node.value,
                )
            else:
                edge = create_edge_model(
                    subject_id=graph_node.id,
                    predicate=predicate,
                    object_id=graph_node.id,  # For literal values, use the node id as the object id
                    object_value=edge_value,
                )
            edges.append(edge)
    return edges


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

        # All edges are object IDs
        property_value["@id"] = edge.object_id

        # If the edge has provenance, add it to the property value
        if edge.provenance:
            property_value["@provenance"] = edge.provenance

        edge_groups[edge.predicate].append(property_value)

    # Add edge groups to properties
    for predicate, values in edge_groups.items():
        # If there's only one value, don't wrap it in a list
        graph_node_properties[predicate] = values[0] if len(values) == 1 else values

    return GraphNode(**graph_node_properties)


def coerce_edge_val_for_db_write(e: EdgeModel, col: str) -> str | None:
    """
    Coerces and truncates edge values to comply with Spanner index limits.
    Args:
      e: The EdgeModel instance containing raw data.
      col: The target database column name.
    Returns:
       - For 'object_value': A UTF-8 string truncated to 4096 bytes (safe-decoded).
        - For 'object_bytes': A Base64-encoded representation of the model's 'object_value'.
        - For other columns: The raw attribute value from the model.
    """
    if col not in ("object_value", "object_bytes"):
        return getattr(e, col)

    val = getattr(e, "object_value")
    if not val:
        return None
    val_bytes = str(val).encode("utf-8")

    # A Spanner index key incorporates both the indexed columns AND the Primary Key.
    # Max index key length is 8192 bytes total. The Primary Keys can swallow up to 4096 bytes easily.
    # So we must restrict object_value to 4096 bytes to guarantee the total key size is < 8192 bytes.
    if col == "object_value":
        if len(val_bytes) > OBJECT_VALUE_MAX_LENGTH:
            # Slice to exactly OBJECT_VALUE_MAX_LENGTH bytes, dropping fragmented chars gracefully
            # TODO: To avoid hash index collisions, we should use a deterministic hash of the object_value
            # and store that along with the truncated value.
            val_truncated = val_bytes[:OBJECT_VALUE_MAX_LENGTH].decode(
                "utf-8", errors="ignore"
            )
            return val_truncated
        return val
    elif col == "object_bytes":
        if len(val_bytes) > OBJECT_VALUE_MAX_LENGTH:
            return base64.b64encode(val_bytes).decode("utf-8")
        return None


def get_node_models(jsonld: JSONLDDocument) -> list[NodeModel]:
    """
    Converts a JSON-LD document into a list of NodeModel instances with their outgoing edges loaded.
    """
    node_models = []
    for graph_node in jsonld.graph:
        node_model = create_node_model(graph_node)
        node_model.outgoing_edges = extract_edges_from_node(graph_node)
        node_models.append(node_model)
    return node_models


def get_node_model_batches(
    node_models: list[NodeModel], batch_size: int = 1000
) -> list[list[NodeModel]]:
    """
    Splits a list of NodeModel instances into batches of nodes and edges.

    Args:
      node_models: List of NodeModel instances
      batch_size: Maximum number of nodes and edges per batch

    Returns:
      List of batches of nodes and edges
    """
    node_batches: list[list[NodeModel]] = []
    current_batch: list[NodeModel] = []
    current_batch_len = 0
    for node_model in node_models:
        node_len = len(node_model.outgoing_edges) + 1

        # If the node itself is larger than the batch_size, add it as its own batch
        if node_len >= batch_size:
            if current_batch:
                node_batches.append(current_batch)
                current_batch = []
                current_batch_len = 0
            node_batches.append([node_model])
            continue

        # Add node and its edges to the current batch
        if current_batch_len + node_len <= batch_size:
            current_batch.append(node_model)
            current_batch_len += node_len
        else:
            # If the current batch is full, add it to the list of batches
            node_batches.append(current_batch)
            current_batch = [node_model]
            current_batch_len = node_len

    # Add the last batch if it's not empty
    if current_batch:
        node_batches.append(current_batch)
    return node_batches


def insert_node_models_batch(
    node_models: list[NodeModel], spanner_batch: database.BatchCheckout
):
    """
    Inserts a batch of NodeModel instances into the database using Spanner API.

    Args:
      node_models: List of NodeModel instances
      spanner_batch: Spanner batch to insert into

    Returns:
      None
    """
    # Get the column names from the NodeModel and EdgeModel
    node_columns = tuple(c.name for c in NodeModel.__table__.columns)
    edge_columns = tuple(
        c.name
        for c in EdgeModel.__table__.columns
        if c.name != "object_value_tokenlist"
    )

    # Insert nodes into the database
    spanner_batch.insert_or_update(
        table=NODE_TABLE_NAME,
        columns=node_columns,
        values=[tuple(getattr(n, col) for col in node_columns) for n in node_models],
    )

    # Delete existing edges for these nodes using a KeyRange prefix
    keyset = spanner.KeySet(
        ranges=[
            spanner.KeyRange(start_closed=[n.subject_id], end_closed=[n.subject_id])
            for n in node_models
        ]
    )
    spanner_batch.delete(table=EDGE_TABLE_NAME, keyset=keyset)

    # Insert the new edges
    for node_model in node_models:
        # Skip if there are no edges to avoid empty insert errors
        if not node_model.outgoing_edges:
            continue
        spanner_batch.insert_or_update(
            table=EDGE_TABLE_NAME,
            columns=edge_columns,
            values=[
                tuple(coerce_edge_val_for_db_write(e, col) for col in edge_columns)
                for e in node_model.outgoing_edges
            ],
        )


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

        config = get_config()
        spanner_client = spanner.Client(project=config.GCP_PROJECT_ID)
        instance = spanner_client.instance(config.GCP_SPANNER_INSTANCE_ID)
        self.spanner_database = instance.database(config.GCP_SPANNER_DATABASE_NAME)

        # Silence Spanner client INFO logs
        self.spanner_database.logger.setLevel(logging.WARNING)

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

        # Load outgoing edges
        query = query.options(joinedload(NodeModel.outgoing_edges)).limit(limit)

        nodes = query.all()
        logger.debug("Retrieved %d nodes with outgoing edges", len(nodes))
        return nodes

    def insert_graph_nodes(
        self, jsonld: JSONLDDocument, batch_size: int = 1000
    ) -> None:
        """
        Inserts nodes and edges from a JSON-LD document into the database using Spanner API.

        Updates the nodes and edges if they already exist.

        Args:
          jsonld: The JSON-LD document containing nodes and edges to insert
        """

        # Convert JSON-LD to NodeModels
        node_models = get_node_models(jsonld)
        node_model_batches = get_node_model_batches(node_models, batch_size)
        total_edges = sum(len(node_model.outgoing_edges) for node_model in node_models)

        logger.info(
            "Inserting %d nodes and %d edges in %d batch(es) to Spanner",
            len(node_models),
            total_edges,
            len(node_model_batches),
        )

        # Insert nodes and edges in batches
        # TODO(dwnoble): this insert may fail if a node in an earlier batch references a node in a later batch.
        # Also may fail if a node references a node that is in a remote knowledge graph
        # Possible solution: Insert all nodes first, then insert all edges in a second pass.
        success_count = 0
        try:
            for node_model_batch in node_model_batches:
                with self.spanner_database.batch() as spanner_batch:
                    insert_node_models_batch(node_model_batch, spanner_batch)
                success_count += len(node_model_batch)
        except Exception as e:
            error_message = f"Failed to insert nodes and edges to Spanner after {success_count}/{len(node_models)} nodes inserted"
            logger.exception(error_message)
            raise GraphServiceError(error_message) from e

        logger.info(
            "Successfully committed %d nodes and %d edges to Spanner",
            success_count,
            total_edges,
        )

    def drop_tables(self) -> None:
        """
        Delete Node and Edge tables from the graph database.
        """
        logger.info("Dropping index EdgeByObjectValue")
        query = "DROP INDEX EdgeByObjectValue"
        self.session.execute(text(query))
        logger.info("Dropping table %s", EDGE_TABLE_NAME)
        query = f"DROP TABLE {EDGE_TABLE_NAME}"
        self.session.execute(text(query))
        logger.info("Dropping table %s", NODE_TABLE_NAME)
        query = f"DROP TABLE {NODE_TABLE_NAME}"
        self.session.execute(text(query))
        self.session.commit()
        logger.info("Successfully dropped Node and Edge tables")
