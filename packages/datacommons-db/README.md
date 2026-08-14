# Data Commons Database Module

This module provides the database models and client primitives for the Data Commons project, implementing a graph database using Google Cloud Spanner and SQLAlchemy. It defines the core data models for nodes, edges, observations, and schema migration version tracking.

## Features

- **Direct Cloud Spanner Client (`SpannerClient`)**: Client for Spanner database operations, DDL execution, parameterized DML, and point-in-time snapshot queries.
- **SQLAlchemy ORM models**: Declarative models for nodes, edges, and observations.
- **Graph database implementation**: Built on top of Google Cloud Spanner.
- **JSON-LD document support**: Model support for data import/export.
- **Efficient indexing & querying**: Full-text and composite indexing for graph traversals.
- **Provenance tracking**: Complete auditability for all graph entities and relationships.

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

### Cloud Spanner Client

The package provides `SpannerClient` for direct Spanner operations, DDL execution, and query execution.

#### Initialization

```python
from datacommons_db.clients import SpannerClient

client = SpannerClient(
    project_id="your-gcp-project",
    instance_id="your-spanner-instance",
    database_id="your-spanner-database",
)
```


#### Checking Tables

```python
# Check if a specific table exists in information_schema
if not client.table_exists("Node"):
    print("Node table not found")
```

#### Executing DDL Statements

`execute_ddl()` accepts a single statement string or a list of statement strings, and waits for Spanner Long-Running Operations (LROs) to complete, returning a `DdlResult`:

```python
# Single statement
ddl_result = client.execute_ddl("""
    CREATE TABLE CustomTable (
        id STRING(64) NOT NULL,
        name STRING(MAX)
    ) PRIMARY KEY (id)
""")
if not ddl_result.success:
    print(f"DDL failed: {ddl_result.error}")

# Multiple statements (pass as a list)
ddl_result = client.execute_ddl([
    "CREATE TABLE TableA (id INT64) PRIMARY KEY (id)",
    "CREATE TABLE TableB (id INT64) PRIMARY KEY (id)",
])
```


#### Executing Queries & DML

```python
from google.cloud import spanner

# Parameterized DML transaction (returns DmlResult)
dml_result = client.execute_dml(
    "UPDATE CustomTable SET name = @name WHERE id = @id",
    params={"name": "New Name", "id": "123"},
    param_types={"name": spanner.param_types.STRING, "id": spanner.param_types.STRING},
)
if dml_result.success:
    print(f"Rows affected: {dml_result.rows_affected}")
else:
    print(f"DML failed: {dml_result.error}")

# Point-in-time Snapshot query (returns QueryResult)
query_result = client.execute_query(
    "SELECT id, name FROM CustomTable WHERE id = @id",
    params={"id": "123"},
    param_types={"id": spanner.param_types.STRING},
)
if query_result.success:
    print(f"Queried rows: {query_result.rows}")
```




### SQLAlchemy ORM Usage

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datacommons_db.models.node import NodeModel
from datacommons_db.models.edge import EdgeModel

# Initialize database connection
engine = create_engine('spanner:///projects/your-project/instances/your-instance/databases/your-database')

# Create a session
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