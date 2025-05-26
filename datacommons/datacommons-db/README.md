# Data Commons Database Module

This module provides the database layer for the Data Commons project, implementing a graph database using Google Cloud Spanner and SQLAlchemy. It handles the storage and retrieval of nodes, edges, and observations in a graph structure.

## Features

- Graph database implementation using Google Cloud Spanner
- SQLAlchemy ORM models for nodes, edges, and observations
- JSON-LD document support for data import/export
- Efficient querying with proper indexing
- Relationship management between nodes and edges
- Provenance tracking for all relationships

## Data Model

### Node Model
- Primary key: `subject_id` (String)
- Properties:
  - `name` (Text)
  - `types` (Array of Strings)
- Relationships:
  - `outgoing_edges`: One-to-many relationship with Edge model

### Edge Model
- Composite primary key: (`subject_id`, `predicate`, `object_id`, `object_hash`, `provenance`)
- Properties:
  - `object_value` (Text)
  - `object_value_tokenlist` (Text, full-text search)
- Relationships:
  - `source_node`: Many-to-one relationship with Node model
- Indexes:
  - `EdgeByObjectValue`: Index on `object_value` for efficient lookups

### Observation Model
- Composite primary key: (`variable_measured`, `observation_about`, `import_name`)
- Properties:
  - `observation_period` (String)
  - `measurement_method` (String)
  - `unit` (String)
  - `scaling_factor` (String)
  - `observations` (LargeBinary)
  - `provenance_url` (String)

## Usage

### Basic Setup

```python
from datacommons.db.spanner import get_spanner_session
from datacommons.db.service import GraphService

# Initialize database session
db = get_spanner_session(project_id, instance_id, database_name)

# Create service instance
graph_service = GraphService(db)

# Query nodes
nodes = graph_service.get_graph_nodes(limit=100, type_filter="Person")

# Insert nodes from JSON-LD
graph_service.insert_graph_nodes(jsonld_document)
```

### JSON-LD Support

The module includes built-in support for JSON-LD format:
- Automatic namespace handling
- Conversion between database models and JSON-LD format
- Support for provenance tracking
- Nested property handling

## Namespaces

The module supports several predefined namespaces:
- `rdf`: http://www.w3.org/1999/02/22-rdf-syntax-ns#
- `rdfs`: http://www.w3.org/2000/01/rdf-schema#
- `xsd`: http://www.w3.org/2001/XMLSchema#
- `dc`: https://datacommons.org/
- `schema`: https://schema.org/

## Performance Considerations

- Deferred loading of `object_value_tokenlist` to optimize memory usage
- Proper indexing on frequently queried fields
- Efficient relationship loading using SQLAlchemy's `joinedload`
- Support for pagination and filtering

## Dependencies

- SQLAlchemy
- Google Cloud Spanner
- Pydantic (for JSON-LD schema validation)

## Contributing

When contributing to this module:
1. Ensure all database operations are properly indexed
2. Maintain JSON-LD compatibility
3. Add appropriate type hints
4. Include docstrings for all public methods
5. Add tests for new functionality

## License

[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)