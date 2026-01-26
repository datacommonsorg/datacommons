# Data Commons Knowledge Graph & Schema Validator Design

## Overview
This document outlines the design for the Data Commons Knowledge Graph (KG) and Schema Validator. The system is designed to provide a flexible, validated graph storage mechanism that ensures data integrity based on Semantic Web standards (RDF, RDFS) and custom schema definitions.

## Core Concepts

### 1. Knowledge Graph (KG)
The Knowledge Graph is the central repository for all schema and data nodes.
- **Single Namespace**: The KG operates under a defined namespace (e.g., `https://knowledge-graph.example.org/`).
- **Unified Storage**: Stores both "Schema" (Classes, Properties) and "Data" (Instances) as nodes in the graph.
- **Strict Validation**: No data can be added to the KG without passing validation checks.

### 2. Schema Validator
The Validator ensures that any data entering the KG conforms to:
- **Standard Primitives**: RDF, RDFS, and XSD types.
- **Custom Schema rules**: Domain, Range, and Class existence checks defined within the KG itself.

---

## Architecture

### Class Diagram

```mermaid
classDiagram

    class KnowledgeGraph {
        +str namespace
        +str default_prefix
        -rdflib.Graph _graph
        -SchemaValidator _validator
        +validate(nodes: List[Dict]) Report
        +add(nodes: List[Dict]) void
    }

    class SchemaValidator {
        +validate_node(node, context_graph)
    }

    KnowledgeGraph --> SchemaValidator : uses
```

## Component Design

### 1. `KnowledgeGraph` (Abstract Base Class)
Defines the contract for all KG implementations.

**Attributes:**
- `namespace`: The base URI for the KG.
- `default_prefix`: The default prefix label (e.g., "ex") that maps to the KG's namespace.

**Methods:**
- `validate(nodes: Union[Dict, List[Dict]]) -> ValidationReport`
    - Checks if the input JSON-LD nodes are valid against the *current* state of the KG.
    - Does *not* modify the graph.
- `add(nodes: Union[Dict, List[Dict]]) -> None`
    - First calls `validate()`.
    - If valid, inserts the nodes into the underlying storage.
    - Raises `ValueError` or custom exception if validation fails.

### 2. `KnowledgeGraph` (Implementation)
A reference implementation using `rdflib.Graph` in memory.

**Storage:**
- Uses an instance of `rdflib.Graph` to store all triples.

**Logic:**
- **Add**: 
    1. Parse input JSON-LD into a temporary graph.
    2. Run validation against the *combined* knowledge (Current Graph + New Data).
        - *Note*: Validation often requires checking if a referenced Class exists. If we are adding a new Class *and* an instance of it simultaneously, the validator must verify them together.
    3. If valid, merge temporary graph into main `_graph`.

### 3. `SchemaValidationService` (The Validator)
Responsible for the core logic of checking RDF/RDFS/XSD constraints.

**Capabilities:**
- **Primitive Checks**:
    - Ensures `rdf:`, `rdfs:`, `xsd:` terms are known and valid (e.g., rejects `rdf:SomeInvalidProperty`).
- **Integrity Checks (Schema)**:
    - **Classes**: Referenced types must exist (e.g., `@type: "ex:Person"` requires `ex:Person` to be defined as `rdfs:Class`).
    - **Properties**: Referenced predicates must exist (e.g., `"ex:age": 30` requires `ex:age` to be defined as `rdf:Property`).
    - **Domains**: Subject must match the property's `rdfs:domain`.
    - **Ranges**: Object must match the property's `rdfs:range` (either a Class or XSD datatype).

## API & Usage Specification

### Initialization
```python
from datacommons_schema.knowledge_graph import KnowledgeGraph

# Initialize an empty KG with a specific namespace
kg = KnowledgeGraph(namespace="http://example.org/")
```

### Adding Schema
Schema is just data. You add it like any other node.
```python
schema_definition = {
    "@context": {
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "ex": "http://example.org/"
    },
    "@graph": [
        {"@id": "ex:Person", "@type": "rdfs:Class"},
        {"@id": "ex:name", "@type": "rdf:Property", "rdfs:domain": {"@id": "ex:Person"}, "rdfs:range": {"@id": "xsd:string"}}
    ]
}

# Validates that 'rdfs:Class' is a known primitive.
# Validates that 'xsd:string' is a known primitive.
kg.add(schema_definition) 
```

### Adding Data
```python
person_node = {
    "@context": {"ex": "http://example.org/"},
    "@id": "ex:Alice",
    "@type": "ex:Person",
    "ex:name": "Alice"
}

# 1. Checks if 'ex:Person' exists in KG (It was added above).
# 2. Checks if 'ex:name' exists in KG.
# 3. Checks if 'ex:Alice' satisfies domain of 'ex:name' (ex:Person).
# 4. Checks if "Alice" satisfies range of 'ex:name' (xsd:string).
kg.add(person_node)
```

### Validation Failure Example
```python
invalid_node = {
    "@context": {"ex": "http://example.org/"},
    "@id": "ex:Bob",
    "ex:unknownProp": "Value" 
}

# Should raise ValidationException:
# "Property 'ex:unknownProp' is not defined in the Knowledge Graph."
kg.add(invalid_node)
```

## Implementation Roadmap

1.  **Refactor `SchemaValidationService`**:
    *   Decouple it from strictly taking a static schema in `__init__`.
    *   Allow it to accept a "Knowledge Store" interface or lookup function to check for existence of terms during validation.
2.  **Implement `KnowledgeGraph` ABC**:
    *   Define the interface.
3.  **Implement `KnowledgeGraph`**:
    *   Wire up `rdflib` and the Validator.
