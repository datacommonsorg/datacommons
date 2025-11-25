# Data Commons Database Module

This module provides the database models for the Data Commons project, implementing a graph database using Google Cloud Spanner and SQLAlchemy. It defines the core data models for nodes, edges, and observations in a graph structure.

## Features

- SQLAlchemy ORM models for nodes, edges, and observations
- Graph database implementation using Google Cloud Spanner
- JSON-LD document support for data import/export
- Efficient querying with proper indexing
- Relationship management between nodes and edges
- Provenance tracking for all relationships

## Data Model

### NodeModel
- Primary key: `subject_id` (String)
- Properties:
  - `name` (Text)
  - `types` (Array of Strings)
- Relationships:
  - `outgoing_edges`: One-to-many relationship with EdgeModel

### EdgeModel
- Composite primary key: (`subject_id`, `predicate`, `object_id`, `object_hash`, `provenance`)
- Properties:
  - `object_value` (Text)
  - `object_value_tokenlist` (Text, full-text search)
- Relationships:
  - `source_node`: Many-to-one relationship with NodeModel
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
from sqlalchemy import create_engine
from datacommons_db.models.node import NodeModel
from datacommons_db.models.edge import EdgeModel

# Initialize database connection
engine = create_engine('spanner:///projects/your-project/instances/your-instance/databases/your-database')

# Create tables
Base.metadata.create_all(engine)

# Create a session
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)
session = Session()

# Example: Query nodes
nodes = session.query(NodeModel).filter(NodeModel.types.contains(['Person'])).limit(100).all()
```

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

## Contributing

When contributing to this module:
1. Ensure all database operations are properly indexed
2. Maintain JSON-LD compatibility
3. Add appropriate type hints
4. Include docstrings for all public methods
5. Add tests for new functionality

## License

[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)