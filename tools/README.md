# Data Commons Platform Developer Tools (`dcp-tools`)

This directory contains internal developer tools and automation utilities for the Data Commons Platform (DCP). These tools are intended exclusively for repository contributors and DevOps workflows, and are not distributed as public packages.

---

## 1. Overview

Internal developer commands are centralized under the unified CLI entrypoint: **`dcp-tools`**.

```bash
uv run dcp-tools [COMMAND] [ARGS]...
```

### Available Command Suites

| Command Suite | Description | Documentation |
| :--- | :--- | :--- |
| **`migrations`** | Create, re-timestamp, and manage Cloud Spanner database schema migrations. | [Schema Migrations Developer Guide](../docs/schema_migrations_developer_guide.md) |

---

## 2. Usage Examples

### Schema Migrations (`dcp-tools migrations`)

```bash
# View general migrations help
uv run dcp-tools migrations --help

# Create a new timestamped migration script
uv run dcp-tools migrations create add_node_tables -d "Add Node and Edge tables"

# Bump / re-timestamp an existing migration to resolve merge conflicts
uv run dcp-tools migrations bump add_node_tables

# Bump by filename with non-interactive confirmation (-y)
uv run dcp-tools migrations bump 20260819135412_add_node_tables.py -y
```

---

## 3. Adding New Developer Tools

To add a new tool or subcommand suite to `dcp-tools`:

1. **Create Tool Directory:**
   Add a subdirectory under `tools/` (e.g. `tools/my_tool/`) with an `__init__.py`.
2. **Define Click Commands:**
   Implement your CLI commands using `click` (e.g. in `tools/my_tool/my_tool_cli.py`).
3. **Register in `tools/cli.py`:**
   Import your command group and register it on the top-level CLI:
   ```python
   from tools.my_tool.my_tool_cli import cli as my_tool_cli

   cli.add_command(my_tool_cli, name="my-tool")
   ```
4. **Declare Dependencies:**
   Add any new runtime dependencies required by your tool to `tools/pyproject.toml`.
5. **Add Tests:**
   Add unit tests under `tools/my_tool/tests/` using `pytest`.

