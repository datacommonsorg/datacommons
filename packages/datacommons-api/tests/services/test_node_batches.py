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

from datacommons_db.models.node import NodeRecord
from datacommons_db.models.edge import EdgeRecord
from datacommons_api.services.graph_service import get_node_model_batches


def test_get_node_model_batches_bug():
    node1 = NodeRecord(subject_id="node1", types=["TypeA"])
    # 5 edges + 1 node = 6 items
    node1.outgoing_edges = [
        EdgeRecord(subject_id="node1", predicate="p", object_id=f"obj{i}")
        for i in range(5)
    ]

    node2 = NodeRecord(subject_id="node2", types=["TypeA"])
    # 5 edges + 1 node = 6 items
    node2.outgoing_edges = [
        EdgeRecord(subject_id="node2", predicate="p", object_id=f"obj{i}")
        for i in range(5)
    ]

    node3 = NodeRecord(subject_id="node3", types=["TypeA"])
    # 5 edges + 1 node = 6 items
    node3.outgoing_edges = [
        EdgeRecord(subject_id="node3", predicate="p", object_id=f"obj{i}")
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
