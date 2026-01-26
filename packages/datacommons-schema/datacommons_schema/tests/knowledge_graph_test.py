import pytest
from rdflib import Graph, URIRef, Literal, RDF, RDFS, XSD
from datacommons_schema.knowledge_graph import KnowledgeGraph
from datacommons_schema.services.schema_validation_service import ValidationError

def test_kg_initialization():
    kg = KnowledgeGraph(namespace="http://example.org/", default_prefix="ex")
    assert kg.namespace == "http://example.org/"
    assert kg.default_prefix == "ex"
    # Check strict prefix binding in internal graph
    assert dict(kg._graph.namespaces())["ex"] == URIRef("http://example.org/")

def test_add_valid_node():
    kg = KnowledgeGraph(namespace="http://example.org/", default_prefix="ex")
    
    # 1. Add Schema (Class and Property)
    # Note: validation of schema primarily checks for "Undefined Property" (if we are checking property existence).
    # But defining a Class uses 'rdf:type', which is ignored/allowed.
    schema_node = {
        "@context": {"ex": "http://example.org/", "rdf": str(RDF), "rdfs": str(RDFS), "xsd": str(XSD)},
        "@graph": [
            {"@id": "ex:Person", "@type": "rdfs:Class"},
            {"@id": "ex:name", "@type": "rdf:Property", "rdfs:domain": {"@id": "ex:Person"}, "rdfs:range": {"@id": "xsd:string"}}
        ]
    }
    kg.add(schema_node)
    
    # 2. Add Valid Data
    person_node = {
        "@context": {"ex": "http://example.org/"},
        "@id": "ex:Alice",
        "@type": "ex:Person",
        "ex:name": "Alice"
    }
    kg.add(person_node)
    
    # Verify triples exist
    assert (URIRef("http://example.org/Alice"), RDF.type, URIRef("http://example.org/Person")) in kg._graph
    assert (URIRef("http://example.org/Alice"), URIRef("http://example.org/name"), Literal("Alice")) in kg._graph

def test_add_invalid_data_undefined_property():
    kg = KnowledgeGraph(namespace="http://example.org/")
    
    # Valid Schema
    kg.add({
        "@context": {"ex": "http://example.org/", "rdfs": str(RDFS)},
        "@id": "ex:Person", "@type": "rdfs:Class"
    })
    
    # Invalid Data (Undefined Property)
    invalid_node = {
        "@context": {"ex": "http://example.org/"},
        "@id": "ex:Bob",
        "@type": "ex:Person",
        "ex:unknownProp": "Value"
    }
    
    with pytest.raises(ValueError) as excinfo:
        kg.add(invalid_node)
    assert "Property not defined in schema" in str(excinfo.value)

def test_add_invalid_data_domain_violation():
    kg = KnowledgeGraph(namespace="http://example.org/")
    
    # Schema
    kg.add({
        "@context": {"ex": "http://example.org/", "rdf": str(RDF), "rdfs": str(RDFS), "xsd": str(XSD)},
        "@graph": [
            {"@id": "ex:Person", "@type": "rdfs:Class"},
            {"@id": "ex:Dog", "@type": "rdfs:Class"},
            {"@id": "ex:name", "@type": "rdf:Property", "rdfs:domain": {"@id": "ex:Person"}, "rdfs:range": {"@id": "xsd:string"}}
        ]
    })
    
    # Invalid Data (Subject is Dog, but domain requires Person)
    dog_node = {
        "@context": {"ex": "http://example.org/"},
        "@id": "ex:Fido",
        "@type": "ex:Dog",
        "ex:name": "Fido"
    }
    
    with pytest.raises(ValueError) as excinfo:
        kg.add(dog_node)
    assert "Subject must be of type <http://example.org/Person>" in str(excinfo.value)

def test_context_aware_validation():
    """
    Test that validation uses existing KG context for type checks.
    """
    kg = KnowledgeGraph(namespace="http://example.org/")
    
    # 1. Define Schema
    kg.add({
        "@context": {"ex": "http://example.org/", "rdf": str(RDF), "rdfs": str(RDFS)},
        "@graph": [
            {"@id": "ex:Person", "@type": "rdfs:Class"},
            {"@id": "ex:knows", "@type": "rdf:Property", "rdfs:domain": {"@id": "ex:Person"}, "rdfs:range": {"@id": "ex:Person"}}
        ]
    })
    
    # 2. Add Alice (Person)
    kg.add({
        "@context": {"ex": "http://example.org/"},
        "@id": "ex:Alice",
        "@type": "ex:Person"
    })
    
    # 3. Add Bob (Person) - separately
    kg.add({
        "@context": {"ex": "http://example.org/"},
        "@id": "ex:Bob",
        "@type": "ex:Person"
    })
    
    # 4. Add Relationship: Alice knows Bob
    # Validation needs to know Alice and Bob are Persons.
    # Alice is in the update batch (implicitly? No, just the relation).
    # Wait, if we just add the relation, we need to know types of subject/object.
    relation_node = {
        "@context": {"ex": "http://example.org/"},
        "@id": "ex:Alice",
        "ex:knows": {"@id": "ex:Bob"}
    }
    
    # This should pass because KG knows Alice and Bob are Persons
    kg.add(relation_node)

def test_schema_integrity_check_failure():
    """
    This test verifies if we are catching schema integrity issues.
    """
    kg = KnowledgeGraph(namespace="http://example.org/")
    
    # Invalid Schema: Domain points to undefined class
    bad_schema = {
        "@context": {"ex": "http://example.org/", "rdf": str(RDF), "rdfs": str(RDFS)},
        "@id": "ex:prop",
        "@type": "rdf:Property",
        "rdfs:domain": {"@id": "ex:GhostClass"} # Undefined
    }
    
    # IF we want this to fail, we must call validate_schema_integrity.
    # Currently it might pass because 'validate' doesn't check domain target existence.
    with pytest.raises(ValueError) as excinfo:
        kg.add(bad_schema)
    assert "Undefined Domain Target" in str(excinfo.value)
    # If it passes, assert that (showing it allows bad schema). 
    # If users WANT it to fail, we must fix implementation.
    
    # Validated that add() blocked the invalid schema.
    # So we do NOT expect the property to be in the graph.
    assert (URIRef("http://example.org/prop"), RDF.type, RDF.Property) not in kg._graph

def test_add_invalid_data_range_violation():
    kg = KnowledgeGraph(namespace="http://example.org/")
    # Schema
    kg.add({
        "@context": {"ex": "http://example.org/", "rdf": str(RDF), "rdfs": str(RDFS), "xsd": str(XSD)},
        "@graph": [
            {"@id": "ex:Person", "@type": "rdfs:Class"},
            {"@id": "ex:Dog", "@type": "rdfs:Class"},
            {"@id": "ex:owner", "@type": "rdf:Property", "rdfs:domain": {"@id": "ex:Dog"}, "rdfs:range": {"@id": "ex:Person"}}
        ]
    })
    
    # Invalid Data (Subject is Dog, but domain requires Person)
    dog_node = {
        "@context": {"ex": "http://example.org/"},
        "@id": "ex:Fido",
        "@type": "ex:Dog",
        "ex:owner": "FidosOwner"
    }
    
    with pytest.raises(ValueError) as excinfo:
        kg.add(dog_node)
    assert "Object must be a resource of type <http://example.org/Person>, but a literal was found" in str(excinfo.value)