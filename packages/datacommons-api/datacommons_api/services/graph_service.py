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
import base64
import logging
import traceback

from typing import Any, Union, List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload
from google.cloud import spanner
from google.cloud.spanner_v1 import database
from datacommons_db.models.node import NodeRecord
from datacommons_db.models.edge import EdgeRecord
from datacommons_schema.models.jsonld import JSONLDDocument, GraphNode

from sqlalchemy import text, exc
from sqlalchemy.orm import Session, joinedload

from datacommons_api.core.config import get_config
from datacommons_api.core.constants import DEFAULT_NODE_FETCH_LIMIT
from datacommons_db.models.edge import EdgeRecord, EDGE_TABLE_NAME
from datacommons_db.models.node import NodeRecord, NODE_TABLE_NAME
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
    "dc": "https://datacommons.org/browser/",
    "schema": "https://schema.org/",
}

LOCAL_NAMESPACE_NAME = "local"
LOCAL_NAMESPACE_URL = f"http://localhost:5000/schema/{LOCAL_NAMESPACE_NAME}/"


# Threshold for Spanner STRING columns (10MB)
# Payloads larger than this or binary payloads are stored in the 'bytes' column.
VALUE_COLUMN_MAX_SIZE_BYTES = 10 * 1024 * 1024

# --- 1. DATA ABSTRACTION & UTILITIES ---

# TODO: should we convert to namespaced id instead of stripping?
def strip_namespace(identifier: str) -> str:
    """Strip all CURIE namespaces from an id."""
    if not identifier: return identifier
    return identifier.split(":")[-1]

def coerce_node_record_value(content: Any) -> dict[str, Any]:
    """
    Coerces input content into the appropriate storage columns for a NodeRecord.
    
    Logic:
    - If str and < 10MB: store in 'value' (STRING).
    - If bytes or > 10MB: store in 'bytes' (BYTES).
    - Unused column is set to None (SQL NULL) for storage efficiency.
    """
    if content is None:
        return {"value": None, "bytes": None}

    if isinstance(content, bytes):
        return {"value": None, "bytes": content}

    # Convert primitives (int, bool, float) to string for literal storage
    str_val = str(content)
    encoded_val = str_val.encode("utf-8")

    if len(encoded_val) < VALUE_COLUMN_MAX_SIZE_BYTES:
        return {"value": str_val, "bytes": None}
    
    return {"value": None, "bytes": encoded_val}

def get_node_record_value(record: Any) -> Union[str, None]:
    """
    Retrieves the logical value from a NodeRecord, abstracting the storage columns.
    Checks the 'bytes' column first as it handles larger/binary content.
    Decodes the bytes to a UTF-8 string before returning.
    """
    if hasattr(record, "bytes") and record.bytes is not None:
        return record.bytes.decode("utf-8")
    
    return getattr(record, "value", None)

def generate_literal_id(content: Any) -> str:
    """
    Generates a deterministic ID for a literal node based on its content.
    Used to de-duplicate literals (e.g., the string "USA" always maps to one ID).
    """
    if content is None:
        content = ""
    
    if isinstance(content, bytes):
        raw_bytes = content
    else:
        raw_bytes = str(content).encode("utf-8")
        
    m = hashlib.md5()
    m.update(raw_bytes)
    return f"dcid:l/{m.hexdigest()}"

# --- 2. INGESTION LOGIC (TRANSFORMING JSON-LD TO SPANNER) ---

def create_node_record(graph_node: GraphNode) -> NodeRecord:
    """
    Maps a high-level GraphNode to a physical NodeRecord.
    Ensures Go-compatible defaults (empty strings/lists instead of NULLs).
    """
    # Use getattr for resilience against dynamic Pydantic attributes
    subject_id = strip_namespace(getattr(graph_node, "id", None))
    name = getattr(graph_node, "name", "") or ""
    
    raw_type = getattr(graph_node, "type", [])
    if isinstance(raw_type, list):
        types = raw_type
    elif raw_type:
        types = [raw_type]
    else:
        types = []

    content_data = coerce_node_record_value(getattr(graph_node, "value", None))

    return NodeRecord(
        subject_id=subject_id,
        name=name,
        types=[strip_namespace(t) for t in types],
        value=content_data["value"],
        bytes=content_data["bytes"]
    )

def create_edge_record(subject_id: str, predicate: str, object_id: str, provenance: str = "") -> EdgeRecord:
    """
    Factory for EdgeRecords. Edges in this model are pure relational pointers.
    """
    if not object_id:
        raise GraphServiceError(f"Missing object_id for edge {subject_id} -> {predicate}.")
    
    return EdgeRecord(
        subject_id=strip_namespace(subject_id),
        predicate=strip_namespace(predicate),
        object_id=strip_namespace(object_id),
        provenance=strip_namespace(provenance)
    )

def extract_edges_from_graph_node(graph_node: GraphNode) -> Tuple[List[EdgeRecord], List[NodeRecord]]:
    """
    Traverses a GraphNode to extract edges and spawn "Literal Nodes".
    """
    subject_id = getattr(graph_node, "id", None)
    provenance = getattr(graph_node, "provenance", "")
    edges = []
    literal_nodes = []

    reserved_keys = {"id", "type", "name", "value", "provenance"}
    properties = graph_node.model_dump(by_alias=True, exclude_none=True)

    for predicate, value in properties.items():
        if predicate in reserved_keys or predicate.startswith("@"):
            continue

        values = value if isinstance(value, list) else [value]

        for val in values:
            if isinstance(val, dict) and "@id" in val:
                # Standard entity reference
                edge_prov = val.get("@provenance", provenance)
                edges.append(create_edge_record(
                    subject_id=subject_id,
                    predicate=predicate,
                    object_id=val["@id"],
                    provenance=edge_prov
                ))
            else:
                # Literal value: Spawn a Literal Node + an Edge pointing to it
                lit_id = generate_literal_id(val)
                literal_nodes.append(NodeRecord(
                    subject_id=lit_id,
                    types=["literal"],
                    **coerce_node_record_value(val)
                ))
                edges.append(create_edge_record(
                    subject_id=subject_id,
                    predicate=predicate,
                    object_id=lit_id,
                    provenance=provenance
                ))

    return (edges, literal_nodes)

# --- 3. EXTRACTION LOGIC (TRANSFORMING SPANNER TO JSON-LD) ---

def node_record_to_graph_node(record: NodeRecord) -> GraphNode:
    """
    The "De-normalizer". Collapses literal nodes back into simple property values
    to hide the underlying storage model from the API user.
    """
    data = {"@id": record.subject_id}
    if record.types:
        data["@type"] = record.types
    if record.name:
        data["name"] = record.name

    val = get_node_record_value(record)
    if val is not None:
        data["value"] = val

    properties = {}
    for edge in record.outgoing_edges:
        predicate = edge.predicate
        target = getattr(edge, "target_node", None)

        if not target:
            prop_val = {"@id": edge.object_id}
        elif "literal" in target.types:
            prop_val = get_node_record_value(target)
        else:
            prop_val = {"@id": target.subject_id}

        if predicate in properties:
            if not isinstance(properties[predicate], list):
                properties[predicate] = [properties[predicate]]
            properties[predicate].append(prop_val)
        else:
            properties[predicate] = prop_val

    data.update(properties)
    return GraphNode(**data)

# --- 4. DATABASE & BATCHING OPERATIONS ---

def get_node_record_batches(nodes: List[NodeRecord], batch_size: int = 1000) -> List[List[NodeRecord]]:
    """
    Splits NodeRecords into batches based on estimated Spanner mutation count.
    """
    batches = []
    current_batch = []
    current_mutation_count = 0

    for node in nodes:
        node_mutations = 1 + len(getattr(node, "outgoing_edges", []))
        if current_mutation_count + node_mutations > batch_size and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_mutation_count = 0
        current_batch.append(node)
        current_mutation_count += node_mutations

    if current_batch:
        batches.append(current_batch)
    return batches

def insert_records_batch(records: List[NodeRecord], spanner_batch: Any):
    """
    Low-level execution of Spanner mutations. 
    Deduplicates nodes and ensures Nodes are inserted before Edges.
    """
    unique_nodes = {node.subject_id: node for node in records}
    all_edges = []
    for node in records:
        all_edges.extend(getattr(node, "outgoing_edges", []))

    node_columns = ["subject_id", "name", "types", "value", "bytes"]
    node_values = [
        [
            n.subject_id, 
            n.name if n.name is not None else '', 
            n.types if n.types is not None else [], 
            n.value, 
            n.bytes
        ] 
        for n in unique_nodes.values()
    ]
    
    if node_values:
        spanner_batch.insert_or_update(table="Node", columns=node_columns, values=node_values)

    edge_columns = ["subject_id", "predicate", "object_id", "provenance"]
    edge_values = [[e.subject_id, e.predicate, e.object_id, e.provenance] for e in all_edges]

    if edge_values:
        spanner_batch.insert_or_update(table="Edge", columns=edge_columns, values=edge_values)

# --- 5. GRAPH SERVICE CLASS ---

class GraphService:
    """
    Public interface for Graph operations.
    """
    def __init__(self, session: Session):
        self.session = session

        # Initialize the Spanner database client using system configuration
        config = get_config()
        client = spanner.Client(project=config.GCP_PROJECT_ID)
        instance = client.instance(config.GCP_SPANNER_INSTANCE_ID)
        self.spanner_db = instance.database(config.GCP_SPANNER_DATABASE_NAME)

    def insert_graph_nodes(self, jsonld: JSONLDDocument):
        """
        Processes a JSON-LD document and performs a batched ingestion.
        """
        all_records = []
        for graph_node in jsonld.graph:
            node_record = create_node_record(graph_node)
            edges, literal_nodes = extract_edges_from_graph_node(graph_node)
            node_record.outgoing_edges = edges
            all_records.append(node_record)
            all_records.extend(literal_nodes)

        if not self.spanner_db:
            raise GraphServiceError("Spanner database client not initialized.")

        # Insert nodes and edges in batches
        # TODO(dwnoble): this insert may fail if a node in an earlier batch references a node in a later batch.
        # Also may fail if a node references a node that is in a remote knowledge graph
        # Possible solution: Insert all nodes first, then insert all edges in a second pass.
        batches = get_node_record_batches(all_records)
        for batch in batches:
            subject_ids = [n.subject_id for n in batch]
            with self.spanner_db.batch() as spanner_batch:
                # Clear existing edges for the subjects in this batch to allow clean replacement
                for sid in subject_ids:
                    spanner_batch.delete(
                        table="Edge",
                        keyset=spanner.KeySet(ranges=[spanner.KeyRange(start_closed=[sid], end_closed=[sid])])
                    )
                insert_records_batch(batch, spanner_batch)

    def get_graph_nodes(self, limit: int = 10, type_filter: Optional[List[str]] = None) -> JSONLDDocument:
        """
        Fetches a subgraph and transforms it back to JSON-LD.
        """
        query = self.session.query(NodeRecord).options(
            joinedload(NodeRecord.outgoing_edges).joinedload(EdgeRecord.target_node)
        )
        
        if type_filter:
            query = query.filter(NodeRecord.types.overlap(type_filter))
            
        records = query.limit(limit).all()
        graph = [node_record_to_graph_node(r) for r in records]
        return JSONLDDocument(
            context={
                "@vocab": LOCAL_NAMESPACE_URL,
                LOCAL_NAMESPACE_NAME: LOCAL_NAMESPACE_URL,
                **BASE_NAMESPACES,
            },
            graph=graph,
        )

    def delete_node(self, subject_id: str):
        """
        Deletes a node. Spanner interleaving triggers a cascading delete of edges.
        """
        if not self.spanner_db:
            raise GraphServiceError("Spanner database client not initialized.")
        
        with self.spanner_db.batch() as batch:
            batch.delete(
                table="Node",
                keyset=spanner.KeySet(keys=[subject_id])
            )

    def drop_tables(self):
        """
        Maintenance cleanup for the Graph schema and data.
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