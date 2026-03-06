import pytest
from unittest.mock import MagicMock, patch, call

from sqlalchemy.orm import Session
from google.cloud import spanner
from datacommons_api.core.config import Config
from datacommons_api.services.graph_service import (
    GraphService,
    GraphServiceError,
    get_node_model_batches,
)
from datacommons_db.models.node import NodeModel
from datacommons_db.models.edge import EdgeModel
from datacommons_schema.models.jsonld import JSONLDDocument, GraphNode


def test_get_node_model_batches():
    node1 = NodeModel(subject_id="n1", types=["T1"])
    node1.outgoing_edges = [
        EdgeModel(subject_id="n1", predicate="p", object_id=f"o{i}") for i in range(5)
    ]

    node2 = NodeModel(subject_id="n2", types=["T1"])
    node2.outgoing_edges = [
        EdgeModel(subject_id="n2", predicate="p", object_id=f"o{i}") for i in range(5)
    ]

    node3 = NodeModel(subject_id="n3", types=["T1"])
    node3.outgoing_edges = [
        EdgeModel(subject_id="n3", predicate="p", object_id=f"o{i}") for i in range(5)
    ]

    # 6 items per node
    # batch size 10 means 10 items max. n1 = 6 items -> batch 0. n2 = 6 items -> batch 1. n3 = 6 items -> batch 2.
    batches = get_node_model_batches([node1, node2, node3], batch_size=10)
    assert len(batches) == 3
    assert batches[0] == [node1]
    assert batches[1] == [node2]
    assert batches[2] == [node3]

    # test a node larger than the batch size (6 items > batch size 5)
    batches = get_node_model_batches([node1, node2], batch_size=5)
    assert len(batches) == 2
    assert batches[0] == [node1]
    assert batches[1] == [node2]

    # Test batch size 12. n1 + n2 = 12 items -> batch 0. n3 = 6 items -> batch 1.
    batches = get_node_model_batches([node1, node2, node3], batch_size=12)
    assert len(batches) == 2
    assert batches[0] == [node1, node2]
    assert batches[1] == [node3]


@pytest.fixture
def mock_session():
    return MagicMock(spec=Session)


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


def test_init(mock_session, mock_config, mock_spanner_client):
    service = GraphService(session=mock_session)
    assert service.session == mock_session
    mock_spanner_client.instance.assert_called_once_with("test-instance")
    mock_spanner_client.instance.return_value.database.assert_called_once_with(
        "test-db"
    )


def test_get_graph_nodes(graph_service, mock_session):
    # Setup mock data
    mock_node = NodeModel(subject_id="test_node", types=["TestType"])
    mock_edge = EdgeModel(
        subject_id="test_node", predicate="test_predicate", object_id="test_target"
    )
    mock_node.outgoing_edges = [mock_edge]

    # Mock the query chain
    mock_query = MagicMock()
    mock_query.options.return_value.limit.return_value.all.return_value = [mock_node]
    # Handle type filter
    mock_query.filter.return_value.params.return_value.options.return_value.limit.return_value.all.return_value = [
        mock_node
    ]
    mock_session.query.return_value = mock_query

    # Test without filter
    result = graph_service.get_graph_nodes(limit=10)

    # Verify
    assert isinstance(result, JSONLDDocument)
    assert len(result.graph) == 1
    assert result.graph[0].id == "test_node"
    assert result.graph[0].type == ["TestType"]
    assert result.graph[0].model_dump(by_alias=True, exclude_none=True)[
        "test_predicate"
    ] == {"@id": "test_target"}

    # Test with filter
    result = graph_service.get_graph_nodes(limit=10, type_filter=["TestType"])
    assert isinstance(result, JSONLDDocument)
    assert len(result.graph) == 1


def test_insert_graph_nodes(graph_service, mock_session, mock_spanner_client):
    # Setup mock data for JSONLD
    graph_node = GraphNode(
        **{
            "@id": "test_node",
            "@type": ["TestType"],
            "test_predicate": {"@id": "test_target"},
        }
    )
    mock_jsonld = JSONLDDocument(
        context={"test": "http://test.com/"}, graph=[graph_node]
    )

    mock_batch = MagicMock()
    mock_database = mock_spanner_client.instance.return_value.database.return_value
    mock_database.batch.return_value.__enter__.return_value = mock_batch

    # Test
    graph_service.insert_graph_nodes(mock_jsonld)

    # Verify
    assert mock_batch.insert_or_update.call_count == 2
    mock_batch.delete.assert_called_once()


def test_insert_graph_nodes_error(graph_service, mock_spanner_client):
    # Setup mock data that triggers an error
    mock_jsonld = JSONLDDocument(
        context={}, graph=[GraphNode(**{"@id": "n1", "@type": "t1"})]
    )

    mock_database = mock_spanner_client.instance.return_value.database.return_value
    mock_database.batch.side_effect = Exception("Spanner Error")

    with pytest.raises(GraphServiceError) as exc_info:
        graph_service.insert_graph_nodes(mock_jsonld)

    assert "Failed to insert nodes and edges to Spanner" in str(exc_info.value)


def test_drop_tables(graph_service, mock_session):
    graph_service.drop_tables()
    assert mock_session.execute.call_count == 3
    mock_session.commit.assert_called_once()
