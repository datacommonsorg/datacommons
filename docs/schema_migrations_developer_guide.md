# Data Commons Schema Migrations Developer Guide

This guide details how developers create, update, and manage Cloud Spanner database schema migrations for the Data Commons Platform using the `manage-migrations` devOps CLI tool.

---

## 1. Overview & Architecture

Data Commons uses Google Cloud Spanner as its relational graph store. Schema migrations live in [`packages/datacommons-db/datacommons_db/migrations/migration_scripts/`](../packages/datacommons-db/datacommons_db/migrations/migration_scripts/) and are executed in strict chronological order based on their UTC timestamps.

### Key Distinction: Authoring vs Execution

| Tool | Purpose | Target |
| :--- | :--- | :--- |
| **`manage-migrations`** | **Developer Authoring Tool**: Scaffolds boilerplate, updates timestamps, and resolves merge conflicts. | Local migration files on disk |
| **`datacommons admin migrate-db`** | **Database Execution Engine**: Connects to Cloud Spanner, queries applied migrations, and executes unapplied `upgrade()` methods. | Live Cloud Spanner instance / emulator |

---

## 2. Migration Script Conventions

Every migration script follows standard repository conventions:

1. **Filename Format:** `YYYYMMDDHHMMSS_<change_name>.py` (14-digit UTC timestamp prefix + snake_case change name).
   - Example: `20260819135412_add_observation_indexes.py`
2. **Base Class:** Subclass of `SchemaMigration` ([`datacommons_db.migrations.base.SchemaMigration`](../packages/datacommons-db/datacommons_db/migrations/base.py)).
3. **Class Attributes:**
   - `description: str`: Human-readable summary of the schema change.
   - `creation_timestamp: str`: UTC ISO-8601 timestamp string (`YYYY-MM-DDTHH:MM:SSZ`) matching the filename prefix.
4. **Upgrade Method:**
   - `def upgrade(self, spanner_client: SpannerClient) -> None`: Contains the DDL or DML logic to apply the schema migration.

---

## 3. Using `manage-migrations`

The `manage-migrations` CLI is registered as a workspace command in [`pyproject.toml`](../pyproject.toml). You can run it with `uv run manage-migrations <command>` or directly as `manage-migrations <command>` if your virtual environment is active.

### A. Creating a New Migration (`create`)

To generate a new timestamped migration script with boilerplate pre-filled:

```bash
uv run manage-migrations create <change_name> [-d/--description "<description>"]
```

#### Examples:

```bash
# Basic creation (description is derived from change name)
uv run manage-migrations create add_node_tables

# Creation with explicit description
uv run manage-migrations create add_edge_indexes -d "Add composite index on Edge object_value and predicate"
```

#### What this does:
1. Sanitizes `<change_name>` to lowercase `snake_case`.
2. Generates the current UTC timestamp (e.g. `20260819173000` and `2026-08-19T17:30:00Z`).
3. Creates `packages/datacommons-db/datacommons_db/migrations/migration_scripts/20260819173000_add_edge_indexes.py`.
4. Populates the file with the Apache 2.0 license header, typed `Migration` class, and empty `upgrade()` method.

---

### B. Resolving Merge Conflicts & Re-timestamping (`bump`)

When multiple developers add migration scripts concurrently, timestamp collisions or out-of-order branches can occur during rebase or merge. 

Use `bump` to refresh an existing migration script with the current UTC timestamp:

```bash
uv run manage-migrations bump <target>
```

The `<target>` argument can be:
- The change name (e.g. `add_edge_indexes`)
- The full filename (e.g. `20260817000000_add_edge_indexes.py`)
- The 14-digit timestamp prefix (e.g. `20260817000000`)
- A relative or absolute file path

To reorder a series of migrations, you could `bump` each of the migration scripts in the order you want them to be run.

Alternatively, you can manually adjust the timestamp prefix in the filename and update the `creation_timestamp` in the `Migration` class.
Migrations will always be run chronologically in timestamp order, so make sure the timestamp prefix is set correctly relative to other migrations.

#### Example Interaction:

```text
$ uv run manage-migrations bump add_edge_indexes

Found migration script: 20260817000000_add_edge_indexes.py
Planned changes:
  - Rename to:      20260819173510_add_edge_indexes.py
  - New timestamp:  2026-08-19T17:35:10Z

Proceed with bump? [y/N]: y
✔ Successfully bumped migration script:
  - Old File:      20260817000000_add_edge_indexes.py
  - New File:      20260819173510_add_edge_indexes.py
  - New Timestamp: 2026-08-19T17:35:10Z
```

#### What this does:
1. Locates the target migration script.
2. Prompts for confirmation showing the planned new filename and timestamp.
3. Updates `creation_timestamp: str = "..."` inside the script.
4. Validates Python syntax using AST parsing.
5. Renames the file on disk to match the new timestamp.

---

### C. Listing Discovered Migrations (`list`)

To inspect all migration scripts in chronological sequence:

```bash
uv run manage-migrations list
```

#### Example Output:

```text
Found 2 migration script(s):

  #    Timestamp (UTC)        Filename                                   Description
  ---- ---------------------- ------------------------------------------ ------------------------------
  1    2026-08-17T00:00:00Z   20260817000000_bootstrap.py                Add SchemaMigrations table to bootstrap schema migrations.
  2    2026-08-19T17:35:10Z   20260819173510_add_edge_indexes.py         Add composite index on Edge object_value and predicate
```

---

## 4. Writing Migration Logic

Open the generated migration file and implement the `upgrade()` method using [`SpannerClient`](../packages/datacommons-db/datacommons_db/clients/spanner_client.py):

```python
from datacommons_db.clients.spanner_client import ExecutionStatus, SpannerClient
from datacommons_db.migrations.base import SchemaMigration


class Migration(SchemaMigration):

    description: str = "Add composite index on Edge object_value and predicate"
    creation_timestamp: str = "2026-08-19T17:35:10Z"

    def upgrade(self, spanner_client: SpannerClient) -> None:
        """Executes forward schema changes to upgrade the database."""
        result = spanner_client.execute_ddl([
            """
            CREATE INDEX EdgeByObjectValueAndPredicate 
            ON Edges(object_value, predicate)
            """
        ])
        if result.status != ExecutionStatus.SUCCESS:
            raise RuntimeError(f"Failed to apply migration: {result.error_message}")
```

### Best Practices:
- **Forward-Only DDL:** Cloud Spanner migrations should execute forward DDL statements (`CREATE TABLE`, `CREATE INDEX`, `ALTER TABLE`).
- **Idempotency & Safety:** Check table/index existence or structure when applicable before destructive changes.
- **Always Check `ExecutionStatus`:** Verify `result.status == ExecutionStatus.SUCCESS` and raise a `RuntimeError` on failure to trigger rollback/abort.

---

## 5. Verification & Testing

Always verify that your migration script conforms to repository standards and passes automated tests:

```bash
# 1. Validate your migration script syntax, timestamps, and structure
uv run pytest packages/datacommons-db/tests/migrations/test_migration_scripts.py

# 2. Run linter and formatting checks
uv run ruff check packages/datacommons-db/datacommons_db/migrations/
uv run ruff format --check
```
