from datacommons_db.models.node import NodeModel
from datacommons_db.models.edge import EdgeModel
from datacommons_api.services.graph_service import get_node_model_batches


def test_get_node_model_batches_bug():
    node1 = NodeModel(subject_id="node1", types=["TypeA"])
    # 5 edges + 1 node = 6 items
    node1.outgoing_edges = [
        EdgeModel(subject_id="node1", predicate="p", object_id=f"obj{i}")
        for i in range(5)
    ]

    node2 = NodeModel(subject_id="node2", types=["TypeA"])
    # 5 edges + 1 node = 6 items
    node2.outgoing_edges = [
        EdgeModel(subject_id="node2", predicate="p", object_id=f"obj{i}")
        for i in range(5)
    ]

    node3 = NodeModel(subject_id="node3", types=["TypeA"])
    # 5 edges + 1 node = 6 items
    node3.outgoing_edges = [
        EdgeModel(subject_id="node3", predicate="p", object_id=f"obj{i}")
        for i in range(5)
    ]

    # Total items = 18. Let's set batch size to 10.
    # Node 1 (6 items) -> Batch 1
    # Node 2 (6 items) -> 6 + 6 = 12 > 10. So it hits the else block. Node 2 is skipped.
    batches = get_node_model_batches([node1, node2, node3], batch_size=10)

    print(f"Number of batches: {len(batches)}")
    for i, batch in enumerate(batches):
        print(f"Batch {i}: {[n.subject_id for n in batch]}")

    all_nodes_in_batches = [n for batch in batches for n in batch]
    print(f"Total nodes returned: {len(all_nodes_in_batches)}")
    print(f"Expected: 3, Actual: {len(all_nodes_in_batches)}")


if __name__ == "__main__":
    test_get_node_model_batches_bug()
