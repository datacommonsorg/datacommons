
from datacommons_api.services.graph_service import node_model_to_graph_node, generate_literal_id
from datacommons_db.models.node import NodeModel
from datacommons_db.models.edge import EdgeModel

def test_node_model_to_graph_node_literal_rehydration():
    # 1. Create the Subject Node
    subject_id = "dcid:person1"
    subject_node = NodeModel(subject_id=subject_id, types=["Person"])

    # 2. Create the Literal Target Node (e.g., name="Alice")
    name_val = "Alice"
    literal_id = generate_literal_id(name_val)
    literal_node = NodeModel(subject_id=literal_id, value=name_val)

    # 3. Create the Edge linking them
    # Note: potential issue - EdgeModel constructor requires object_id,
    # but doesn't take target_node directly. We set it manually to simulate joinedload.
    edge = EdgeModel(
        subject_id=subject_id,
        predicate="name",
        object_id=literal_id
    )
    
    # 4. Simulate the result of joinedload by manually populating the relationship
    edge.target_node = literal_node
    subject_node.outgoing_edges = [edge]

    # Act
    graph_node = node_model_to_graph_node(subject_node)

    # Assert
    assert graph_node.id == subject_id
    # The 'name' property should have @value because the target node has a value
    props = graph_node.model_dump(by_alias=True, exclude_none=True)
    assert "name" in props
    # It might be a list or single dict depending on implementation
    name_prop = props["name"]
    if isinstance(name_prop, list):
        name_prop = name_prop[0]
    
    assert name_prop["@value"] == "Alice"
    assert "@id" not in name_prop

def test_node_model_to_graph_node_reference_rehydration():
    # 1. Create the Subject Node
    subject_id = "dcid:person1"
    subject_node = NodeModel(subject_id=subject_id, types=["Person"])

    # 2. Create a Reference Target Node (another Person)
    friend_id = "dcid:person2"
    friend_node = NodeModel(subject_id=friend_id, types=["Person"]) 
    # Important: value is None for reference nodes

    # 3. Create the Edge
    edge = EdgeModel(
        subject_id=subject_id,
        predicate="friend",
        object_id=friend_id
    )

    # 4. Simulate joinedload
    edge.target_node = friend_node
    subject_node.outgoing_edges = [edge]

    # Act
    graph_node = node_model_to_graph_node(subject_node)

    # Assert
    props = graph_node.model_dump(by_alias=True, exclude_none=True)
    assert "friend" in props
    friend_prop = props["friend"]
    if isinstance(friend_prop, list):
        friend_prop = friend_prop[0]
    
    # Needs to be a reference (@id), NOT a literal (@value)
    assert friend_prop["@id"] == friend_id
    assert "@value" not in friend_prop
