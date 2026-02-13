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

from datacommons_api.services.graph_service import extract_edges_from_node, generate_literal_id
from datacommons_db.models.edge import EdgeModel
from datacommons_db.models.node import NodeModel
from datacommons_schema.models.jsonld import GraphNode


def test_extract_edges_from_node_with_literal():
    """
    Test that literal values (strings, numbers, booleans) are extracted as
    separate NodeModels with a generated ID, and linked via an EdgeModel.

    Expected Outcome:
    - For each literal property (name, age, is_student), a new NodeModel is created.
    - The ID of this new NodeModel is a deterministic hash of the literal value.
    - An EdgeModel is created linking the subject node to this new literal node.
    - Total: 3 literal nodes + 3 edges = 6 models.
    """
    # Arrange
    graph_node_data = {
        "@id": "dcid:person1",
        "@type": ["Person"],
        "name": "Alice",
        "age": 30,
        "is_student": True,
    }
    graph_node = GraphNode(**graph_node_data)

    # Act
    models = extract_edges_from_node(graph_node)

    # Assert
    assert len(models) == 6  # 3 edges + 3 literal nodes

    edges = [m for m in models if isinstance(m, EdgeModel)]
    nodes = [m for m in models if isinstance(m, NodeModel)]

    assert len(edges) == 3
    assert len(nodes) == 3

    # Check the 'name' edge and literal node
    name_literal_str = "Alice"
    name_literal_id = generate_literal_id(name_literal_str)
    
    name_edge = next(e for e in edges if e.predicate == "name")
    assert name_edge.subject_id == "dcid:person1"
    assert name_edge.object_id == name_literal_id

    name_node = next(n for n in nodes if n.subject_id == name_literal_id)
    assert name_node.value == name_literal_str

    # Check the 'age' edge and literal node
    age_literal_str = "30"
    age_literal_id = generate_literal_id(age_literal_str)

    age_edge = next(e for e in edges if e.predicate == "age")
    assert age_edge.subject_id == "dcid:person1"
    assert age_edge.object_id == age_literal_id

    age_node = next(n for n in nodes if n.subject_id == age_literal_id)
    assert age_node.value == age_literal_str

    # Check the 'is_student' edge and literal node
    student_literal_str = "True"
    student_literal_id = generate_literal_id(student_literal_str)

    student_edge = next(e for e in edges if e.predicate == "is_student")
    assert student_edge.subject_id == "dcid:person1"
    assert student_edge.object_id == student_literal_id

    student_node = next(n for n in nodes if n.subject_id == student_literal_id)
    assert student_node.value == student_literal_str


def test_extract_edges_from_node_with_reference():
    """
    Test that nested dictionary values (representing other nodes) are treated
    as references and linked directly via their ID.

    Expected Outcome:
    - The nested 'friend' node has an @id, so it is treated as a reference.
    - NO new literal NodeModel should be created for the 'friend' property.
    - An EdgeModel is created linking the subject node to the friend's ID.
    - Total: 1 edge = 1 model.
    """
    # Arrange
    graph_node_data = {
        "@id": "dcid:person1",
        "@type": ["Person"],
        "friend": {
            "@id": "dcid:person2",
            "@type": ["Person"],
            "name": "Bob",
        },
    }
    graph_node = GraphNode(**graph_node_data)

    # Act
    models = extract_edges_from_node(graph_node)

    # Assert
    assert len(models) == 1  # 1 edge, no artificial literal nodes

    edge = models[0]
    assert isinstance(edge, EdgeModel)
    assert edge.subject_id == "dcid:person1"
    assert edge.predicate == "friend"
    assert edge.object_id == "dcid:person2"
