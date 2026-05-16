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

import pytest
import hashlib
from unittest.mock import MagicMock, patch, call

from sqlalchemy.orm import Session
from google.cloud import spanner
from datacommons_api.core.config import Config
from datacommons_api.services.graph_service import (
    GraphService,
    GraphServiceError,
    normalize_graph_id,
    get_node_record_batches,
    generate_literal_id,
    coerce_node_record_value,
    get_value_from_node_record,
    create_node_record,
    create_edge_record,
    extract_edges_from_graph_node,
    node_record_to_graph_node,
    insert_records_batch,
)
from datacommons_db.models.node import NodeRecord
from datacommons_db.models.edge import EdgeRecord
from datacommons_schema.models.jsonld import JSONLDDocument, GraphNode

# --- 1. UNIT TESTS ---


def test_normalize_graph_id():
    # 1. Known Shortforms (Remote)
    assert normalize_graph_id("schema:Person") == ("schema:Person", True)
    assert normalize_graph_id("dc:Place") == ("dc:Place", True)

    # 2. Full URIs -> Shortforms (Remote)
    assert normalize_graph_id("http://schema.org/Person") == ("schema:Person", True)
    assert normalize_graph_id("https://schema.org/Person") == ("schema:Person", True)
    assert normalize_graph_id("https://datacommons.org/browser/Place") == (
        "dc:Place",
        True,
    )

    # 3. Generated Literals (Local, do not strip prefix)
    assert normalize_graph_id("l/123xyz") == ("l/123xyz", False)

    # 4. Standard Local Nodes (Strip prefixes)
    assert normalize_graph_id("dcid:California") == ("California", False)
    assert normalize_graph_id("name") == ("name", False)
    assert normalize_graph_id("") == ("", False)
    assert normalize_graph_id(None) == (None, False)


def test_normalize_graph_id_with_context():
    custom_context = {
        "custom": "http://custom.org/",
        "dcid": "https://datacommons.org/browser/",
    }

    # 1. New Custom Prefix
    assert normalize_graph_id("http://custom.org/Entity", custom_context) == (
        "custom:Entity",
        True,
    )
    assert normalize_graph_id("custom:Entity", custom_context) == (
        "custom:Entity",
        True,
    )

    # 2. Overridden Prefix (dcid is normally stripped, now treated as remote shortform if fully specified)
    assert normalize_graph_id(
        "https://datacommons.org/browser/Place", custom_context
    ) == ("dcid:Place", True)


# 1.1 Content Abstraction
def test_coerce_node_record_value_small():
    content = "Hello World"
    result = coerce_node_record_value(content)
    assert result["value"] == "Hello World"
    assert result["bytes"] == b""


def test_coerce_node_record_value_large():
    content = "a" * (11 * 1024 * 1024)  # 11MB
    result = coerce_node_record_value(content)
    assert result["value"] == ""
    assert result["bytes"] == content.encode("utf-8")


def test_coerce_node_record_value_binary():
    # Example logic using arbitrary bytes
    content = b"\x00\x01"
    result = coerce_node_record_value(content)
    assert result["value"] == ""
    assert result["bytes"] == content


def test_node_record_value_round_trip():
    s = "Round Trip Test"
    record = NodeRecord(**coerce_node_record_value(s))
    assert get_value_from_node_record(record) == s


def test_get_value_from_node_record_decodes_bytes():
    record = NodeRecord(subject_id="n1", bytes=b"Decoded String")
    assert get_value_from_node_record(record) == "Decoded String"


# 1.2 ID Generation
def test_generate_literal_id_determinism():
    val = "California"
    id1 = generate_literal_id(val)
    id2 = generate_literal_id(val)
    assert id1 == id2
    assert id1.startswith("l/")


def test_generate_literal_id_collision():
    assert generate_literal_id("A") != generate_literal_id("B")


# 1.3 Model Mapping
def test_create_node_record_standard():
    # Use @ aliases in constructor for GraphNode compatibility
    gn = GraphNode(**{"@id": "dcid:California", "@type": ["schema:State"]})
    record = create_node_record(gn)
    assert record.subject_id == "California"
    assert record.types == ["schema:State"]


def test_create_node_record_go_defaults():
    gn = GraphNode(**{"@id": "n1", "@type": "t1"})
    record = create_node_record(gn)
    assert record.name == ""  # Go compatibility: empty string, not None
    assert isinstance(record.types, list)


def test_create_node_record_content_mapping():
    gn = GraphNode(**{"@id": "n1", "@type": "t1", "value": "Some Data"})
    record = create_node_record(gn)
    assert record.value == "Some Data"
    assert record.bytes == b""


# 1.4 Ingestion & Edge Logic
def test_extract_edges_from_graph_node_mixed():
    gn = GraphNode(**{"@id": "n1", "p1": {"@id": "target_n"}, "p2": "literal_val"})
    edges, synthesized_nodes = extract_edges_from_graph_node(gn)

    assert len(edges) == 2
    # 1 Literal node + 1 Default Provenance Node
    assert len(synthesized_nodes) == 2
    # The literal node gets appended first in the extraction loop
    # Wait, the fallback prov is generated before the loop in graph_service.py line 242!
    assert synthesized_nodes[0].types == ["system:DefaultNode"]
    assert synthesized_nodes[1].types == ["literal"]


def test_create_edge_record_validation():
    with pytest.raises(GraphServiceError) as excinfo:
        create_edge_record(subject_id="s", predicate="p", object_id=None)
    assert "Missing object_id" in str(excinfo.value)


def test_create_edge_record_success():
    edge = create_edge_record("s", "p", "o", "prov")
    assert edge.subject_id == "s"
    assert edge.predicate == "p"
    assert edge.object_id == "o"
    assert edge.provenance == "prov"


def test_extract_edges_from_graph_node_granular_provenance():
    # Setup a GraphNode with top-level provenance and an edge with its own granular provenance
    gn = GraphNode(
        **{
            "@id": "n1",
            "provenance": "prov:top_level_prov",
            "p1": {"@id": "target_n", "@provenance": "prov:edge_level_prov"},
        }
    )

    edges, synthesized_nodes = extract_edges_from_graph_node(gn)

    assert len(edges) == 1
    assert edges[0].provenance == "edge_level_prov", (
        "Expected edge-level provenance to override top-level provenance"
    )


# 1.5 Extraction Logic
def test_node_record_to_graph_node_collapse():
    lit_id = generate_literal_id("Value")
    lit_node = NodeRecord(subject_id=lit_id, types=["literal"], value="Value")

    source = NodeRecord(subject_id="s1", types=["T"])
    edge = EdgeRecord(subject_id="s1", predicate="name", object_id=lit_id)
    edge.target_node = lit_node
    source.outgoing_edges = [edge]

    gn = node_record_to_graph_node(source)
    assert gn.model_dump(by_alias=True, exclude_none=True)["name"] == {
        "@value": "Value"
    }


def test_node_record_to_graph_node_preserve():
    target = NodeRecord(subject_id="t1", types=["Entity"])
    source = NodeRecord(subject_id="s1", types=["T"])
    edge = EdgeRecord(subject_id="s1", predicate="knows", object_id="t1")
    edge.target_node = target
    source.outgoing_edges = [edge]

    gn = node_record_to_graph_node(source)
    assert gn.model_dump(by_alias=True, exclude_none=True)["knows"] == {"@id": "t1"}


# --- 2. INTEGRATION TESTS ---


@pytest.fixture
def mock_session():
    return MagicMock(spec=Session)


@pytest.fixture
def mock_spanner_batch():
    return MagicMock()


@pytest.fixture
def mock_config():
    with patch("datacommons_api.services.graph_service.get_config") as mock:
        mock_config_instance = MagicMock(spec=Config)
        mock_config_instance.GCP_PROJECT_ID = "test-project"
        mock_config_instance.GCP_SPANNER_INSTANCE_ID = "test-instance"
        mock_config_instance.GCP_SPANNER_DATABASE_NAME = "test-db"
        mock.return_value = mock_config_instance
        yield mock


@pytest.fixture
def mock_spanner_client():
    with patch("datacommons_api.services.graph_service.spanner.Client") as mock:
        mock_client_instance = MagicMock()
        mock_instance = MagicMock()
        mock_database = MagicMock()
        mock_client_instance.instance.return_value = mock_instance
        mock_instance.database.return_value = mock_database
        mock.return_value = mock_client_instance
        yield mock_client_instance


@pytest.fixture
def graph_service(mock_session, mock_config, mock_spanner_client):
    return GraphService(session=mock_session)


def test_insert_records_batch_deduplication(mock_spanner_batch):
    lit = NodeRecord(subject_id="l/shared", types=["literal"], value="USA")
    n1 = NodeRecord(subject_id="n1", types=["T"])
    n2 = NodeRecord(subject_id="n2", types=["T"])

    insert_records_batch([n1, n2, lit, lit], mock_spanner_batch)

    node_calls = [
        c
        for c in mock_spanner_batch.insert_or_update.call_args_list
        if c.kwargs["table"] == "Node"
    ]
    node_values = node_calls[0].kwargs["values"]
    ids = [v[0] for v in node_values]
    assert len(ids) == 3
    assert ids.count("l/shared") == 1


def test_insert_records_batch_order(mock_spanner_batch):
    n1 = NodeRecord(subject_id="n1", types=["T"])
    e1 = EdgeRecord(subject_id="n1", predicate="p", object_id="o")
    n1.outgoing_edges = [e1]

    insert_records_batch([n1], mock_spanner_batch)

    calls = mock_spanner_batch.insert_or_update.call_args_list
    assert calls[0].kwargs["table"] == "Node"
    assert calls[1].kwargs["table"] == "Edge"


def test_get_node_record_batches_splitting():
    nodes = [NodeRecord(subject_id=f"n{i}") for i in range(10)]
    for n in nodes:
        n.outgoing_edges = [
            EdgeRecord(subject_id=n.subject_id, predicate="p", object_id="o")
        ]

    batches = get_node_record_batches(nodes, batch_size=5)
    assert len(batches) == 5
    for b in batches:
        assert len(b) == 2


# 2.2 Cascading & Cleanup
def test_drop_tables_logic(mock_session):
    with patch("datacommons_api.services.graph_service.get_config"):
        with patch("datacommons_api.services.graph_service.spanner.Client"):
            from datacommons_api.services.graph_service import GraphService

            service = GraphService(session=mock_session)
            service.drop_tables()

            calls = [str(c[0][0]).upper() for c in mock_session.execute.call_args_list]
            assert any("DROP TABLE EDGE" in c for c in calls)
            assert any("DROP TABLE NODE" in c for c in calls)


def test_node_deletion_cascade(graph_service, mock_spanner_batch):
    # Setup mock database behavior for the service instance
    mock_database = MagicMock()
    mock_database.batch.return_value.__enter__.return_value = mock_spanner_batch

    # Set the attribute manually since it might not be initialized in the base GraphService yet
    graph_service.spanner_db = mock_database

    # Action: Delete a node
    graph_service.delete_node("test_node_id")

    # Verify: Delete called on 'Node' table.
    mock_spanner_batch.delete.assert_called()
    node_delete = next(
        c
        for c in mock_spanner_batch.delete.call_args_list
        if c.kwargs["table"] == "Node"
    )
    assert node_delete.kwargs["keyset"].keys == ["test_node_id"]


# 2.3 Go-Consumer Compatibility
def test_strict_non_nulls(mock_spanner_batch):
    n1 = NodeRecord(subject_id="n1", types=["T"])
    insert_records_batch([n1], mock_spanner_batch)
    node_call = next(
        c
        for c in mock_spanner_batch.insert_or_update.call_args_list
        if c.kwargs["table"] == "Node"
    )
    values = node_call.kwargs["values"][0]
    # Check that placeholders like '' exist where expected and None is avoided in PK/Metadata
    assert "" in values
    assert b"" in values
    assert None not in values[0:2]


# --- 3. END-TO-END TESTS ---


def test_jsonld_round_trip(graph_service, mock_session, mock_spanner_batch):
    original_json = {
        "@id": "geoId/06",
        "@type": ["State"],
        "name": "California",
        "containedInPlace": {"@id": "geoId/USA"},
    }
    original_doc = JSONLDDocument(context={}, graph=[GraphNode(**original_json)])

    lit_id = generate_literal_id("California")
    lit_node = NodeRecord(subject_id=lit_id, types=["literal"], value="California")
    root = NodeRecord(subject_id="geoId/06", types=["State"])
    e1 = EdgeRecord(subject_id="geoId/06", predicate="name", object_id=lit_id)
    e1.target_node = lit_node
    e2 = EdgeRecord(
        subject_id="geoId/06", predicate="containedInPlace", object_id="geoId/USA"
    )
    e2.target_node = NodeRecord(subject_id="geoId/USA", types=["Country"])
    root.outgoing_edges = [e1, e2]

    mock_query = MagicMock()
    mock_query.options.return_value.limit.return_value.all.return_value = [root]
    mock_session.query.return_value = mock_query

    graph_service.insert_graph_nodes(original_doc)
    retrieved = graph_service.get_graph_nodes(limit=1)

    result_json = retrieved.graph[0].model_dump(by_alias=True, exclude_none=True)
    assert result_json["@id"] == "geoId/06"
    assert result_json["name"] == {"@value": "California"}
    assert result_json["containedInPlace"] == {"@id": "geoId/USA"}


def test_insert_graph_nodes_proxy_synthesis(
    graph_service, mock_session, mock_spanner_batch
):
    """
    Tests that when an edge points to a remote/external ID,
    a Proxy Node is synthesized and inserted alongside the primary node.
    """
    # 1. Provide an input that references an external schema ID
    original_json = {
        "@id": "geoId/NewYork",
        "@type": ["schema:State"],
        "name": "New York",
        # Points to a remote schema namespace
        "containedInPlace": {"@id": "schema:Country"},
    }
    original_doc = JSONLDDocument(context={}, graph=[GraphNode(**original_json)])

    # Setup the spanner_db mock explicitly to ensure the batch context works
    mock_database = MagicMock()
    mock_database.batch.return_value.__enter__.return_value = mock_spanner_batch
    graph_service.spanner_db = mock_database

    # 2. Run insertion
    graph_service.insert_graph_nodes(original_doc)

    # 3. Verify exactly how insert_or_update was called
    node_calls = [
        c
        for c in mock_spanner_batch.insert_or_update.call_args_list
        if c.kwargs["table"] == "Node"
    ]
    edge_calls = [
        c
        for c in mock_spanner_batch.insert_or_update.call_args_list
        if c.kwargs["table"] == "Edge"
    ]

    assert len(node_calls) == 1
    assert len(edge_calls) == 1

    # 4. Inspect the inserted Node values
    node_values = node_calls[0].kwargs["values"]
    inserted_node_ids = set()
    proxy_found = False

    for row in node_values:
        subj_id = row[0]
        types = row[
            4
        ]  # Based on NodeRecord __table__.columns (subject_id, name, value, bytes, types)
        inserted_node_ids.add(subj_id)

        # Verify if the proxy node is in the Node insertions
        if subj_id == "schema:Country":
            proxy_found = True
            assert types == ["schema:ExternalProxy"]  # Verifying the tag logic!

    assert "geoId/NewYork" in inserted_node_ids
    assert proxy_found, "Proxy node for schema:Country was not generated or inserted"

    # 5. Check edge points appropriately
    edge_values = edge_calls[0].kwargs["values"]
    found_edge = False
    for row in edge_values:
        if row[0] == "geoId/NewYork" and row[2] == "schema:Country":
            found_edge = True
    assert found_edge, "Edge pointing to proxy node was not correctly formatted"
