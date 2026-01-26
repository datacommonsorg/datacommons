# Copyright 2026 Google LLC.
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
from rdflib import URIRef, XSD, Graph
from pydantic import BaseModel
from typing import List
import json

from datacommons_schema.services.schema_validation_service import SchemaValidationService

# --- MOCKING MISSING CLASSES FOR THE TEST TO RUN ---
class SchemaError(BaseModel):
    subject: str
    issue: str
    message: str

class SchemaReport(BaseModel):
    is_valid: bool
    errors: List[SchemaError] = []
# ---------------------------------------------------

# ==========================================
# FIXTURES
# ==========================================

def load_graph(schema: dict) -> Graph:
    graph = Graph()
    graph.parse(data=json.dumps(schema), format="json-ld")
    return graph

@pytest.fixture
def sample_schema_dict() -> dict:
    """
    A schema defining:
    - Classes: Person, Organization
    - Properties: name (string), age (int), worksFor (link to Organization)
    """
    return {
        "@context": {
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "ex": "http://example.org/"
        },
        "@graph": [
            {"@id": "ex:Person", "@type": "rdfs:Class"},
            {"@id": "ex:Organization", "@type": "rdfs:Class"},
            {
                "@id": "ex:name",
                "@type": "rdf:Property",
                "rdfs:domain": {"@id": "ex:Person"},
                "rdfs:range": {"@id": "xsd:string"}
            },
            {
                "@id": "ex:age",
                "@type": "rdf:Property",
                "rdfs:domain": {"@id": "ex:Person"},
                "rdfs:range": {"@id": "xsd:integer"}
            },
            {
                "@id": "ex:worksFor",
                "@type": "rdf:Property",
                "rdfs:domain": {"@id": "ex:Person"},
                "rdfs:range": {"@id": "ex:Organization"}
            }
        ]
    }

@pytest.fixture
def schema_service(sample_schema_dict: dict) -> SchemaValidationService:
    """Initializes the service with the valid sample schema."""
    graph = Graph()
    graph.parse(data=json.dumps(sample_schema_dict), format="json-ld")
    return SchemaValidationService(graph)

@pytest.fixture
def valid_data_packet() -> Graph:
    """Data that perfectly conforms to sample_schema_dict."""
    graph = Graph()
    graph.parse(data=json.dumps({
        "@context": {
            "ex": "http://example.org/",
            "xsd": "http://www.w3.org/2001/XMLSchema#"
        },
        "@id": "ex:Alice",
        "@type": "ex:Person",
        "ex:name": "Alice",
        "ex:age": 30,
        "ex:worksFor": {
            "@id": "ex:Google",
            "@type": "ex:Organization"
        }
    }), format="json-ld")
    return graph

# ==========================================
# TESTS
# ==========================================

def test_initialization_extracts_rules(schema_service: SchemaValidationService):
    """Ensure the constructor parses the graph and extracts rules correctly."""
    rules = schema_service.rules
    
    # Check Classes
    assert URIRef("http://example.org/Person") in rules.classes
    assert URIRef("http://example.org/Organization") in rules.classes
    
    # Check Properties
    assert URIRef("http://example.org/name") in rules.properties
    
    # Check Domain/Range logic
    name_prop = URIRef("http://example.org/name")
    assert rules.domains[name_prop] == URIRef("http://example.org/Person")
    assert rules.ranges[name_prop] == XSD.string

def test_schema_integrity_valid(schema_service):
    """Ensure a coherent schema passes integrity checks."""
    report = schema_service.validate_schema_integrity()
    assert report.is_valid is True
    assert len(report.errors) == 0

def test_schema_integrity_invalid():
    """Ensure a schema referencing undefined classes fails integrity checks."""
    bad_schema = {
        "@context": {
            "ex": "http://example.org/",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        },
        "@graph": [
            {"@id": "ex:hasPet", "@type": "rdf:Propertyzzz", "rdfs:domain": {"@id": "ex:GhostClass"}}
        ]
    }
    graph = load_graph(bad_schema)
    service = SchemaValidationService(graph)
    report = service.validate_schema_integrity()

    assert report.is_valid is False
    # We might get multiple errors (one for rdf:Property, maybe others), but at least one should be about malformed URI
    issues = [e.issue for e in report.errors]
    assert "Unknown RDF Term" in issues

def test_schema_integrity_invalid_xsd():
    """Ensure a schema referencing undefined XSD types fails integrity checks."""
    bad_schema = {
        "@context": {
            "ex": "http://example.org/",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "xsd": "http://www.w3.org/2001/XMLSchema#"
        },
        "@graph": [
            {
                "@id": "ex:age", 
                "@type": "rdf:Property", 
                "rdfs:range": {"@id": "xsd:InvalidType"}
            }
        ]
    }
    graph = load_graph(bad_schema)
    service = SchemaValidationService(graph)
    report = service.validate_schema_integrity()
    
    assert report.is_valid is False
    issues = [e.issue for e in report.errors]
    assert "Unknown XSD Term" in issues

def test_validate_valid_data(schema_service, valid_data_packet):
    """Happy path: Data conforms to schema."""
    report = schema_service.validate(valid_data_packet)
    assert report.is_valid is True
    assert report.error_count == 0

def test_validate_undefined_property(schema_service):
    """Test data containing a property not in the schema."""
    data = {
        "@context": {"ex": "http://example.org/"},
        "@id": "ex:Bob",
        "ex:favoriteColor": "Blue" # Not in schema
    }
    graph = load_graph(data)
    report = schema_service.validate(graph)
    
    assert report.is_valid is False
    assert report.errors[0].rule_type == "Undefined Property"
    assert "favoriteColor" in report.errors[0].predicate

def test_validate_domain_violation(schema_service):
    """Test data where subject is wrong type (Organization has an age?)."""
    data = {
        "@context": {"ex": "http://example.org/"},
        "@id": "ex:MegaCorp",
        "@type": "ex:Organization", # Schema says 'age' belongs to 'Person'
        "ex:age": 100
    }
    graph = load_graph(data)
    report = schema_service.validate(graph)
    
    assert report.is_valid is False
    error = report.errors[0]
    assert error.rule_type == "Domain Violation"
    assert "must be of type <http://example.org/Person>" in error.message

def test_validate_range_violation_literal(schema_service):
    """Test data where literal datatype is wrong (age is string instead of int)."""
    data = {
        "@context": {"ex": "http://example.org/"},
        "@id": "ex:Bob",
        "@type": "ex:Person",
        "ex:age": "Thirty" # Should be integer
    }
    graph = load_graph(data)
    report = schema_service.validate(graph)
    
    assert report.is_valid is False
    assert report.errors[0].rule_type == "Range Violation"
    # Note: RDFLib might interpret "Thirty" as xsd:string by default if un-typed

def test_validate_range_violation_class(schema_service):
    """Test data where object URI is the wrong class."""
    data = {
        "@context": {"ex": "http://example.org/"},
        "@id": "ex:Bob",
        "@type": "ex:Person",
        "ex:worksFor": {
            "@id": "ex:AnotherPerson",
            "@type": "ex:Person" # Schema says worksFor range is Organization
        }
    }
    graph = load_graph(data)
    report = schema_service.validate(graph)
    
    assert report.is_valid is False
    assert report.errors[0].rule_type == "Range Violation"
    assert "must be of type <http://example.org/Organization>" in report.errors[0].message