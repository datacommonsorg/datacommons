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

"""SQL utility functions for database schema parsing, template rendering, and statement extraction."""

from pathlib import Path


def render_schema_template(
    template_sql: str,
    *,
    project_id: str,
    location: str = "us-central1",
    embedding_table: str = "NodeEmbedding",
    embedding_index: str = "NodeEmbeddingIndex",
    embedding_label_index: str = "NodeEmbeddingLabelIndex",
    embedding_space: int = 768,
    models: list[dict[str, str]] | None = None,
) -> str:
    """Renders placeholders and CREATE MODEL blocks in the baseline schema template.

    Args:
        template_sql: The raw SQL template string containing Jinja-style placeholders.
        project_id: GCP project ID hosting the Vertex AI endpoint.
        location: GCP region for model endpoints. Defaults to 'us-central1'.
        embedding_table: Name of the vector embedding table. Defaults to 'NodeEmbedding'.
        embedding_index: Name of the vector search index. Defaults to 'NodeEmbeddingIndex'.
        embedding_label_index: Name of the secondary index on embedding label.
        embedding_space: Dimensionality of embedding vectors. Defaults to 768.
        models: Optional list of model configuration dicts with 'name' and 'endpoint'.

    Returns:
        Rendered SQL script string ready for statement parsing.
    """
    resolved_models = models or [
        {"name": "NodeEmbeddingModel", "endpoint": "text-embedding-005"}
    ]

    rendered = (
        template_sql.replace("{{ embedding_table }}", embedding_table)
        .replace("{{ embedding_index }}", embedding_index)
        .replace("{{ embedding_label_index }}", embedding_label_index)
        .replace("{{ embedding_space }}", str(embedding_space))
    )

    if "{% for model in models %}" in rendered:
        model_ddls: list[str] = []
        for m in resolved_models:
            m_name = m["name"]
            m_endpoint = m["endpoint"]
            if not m_endpoint.startswith("//"):
                m_endpoint = (
                    f"//aiplatform.googleapis.com/projects/{project_id}"
                    f"/locations/{location}/publishers/google/models/{m_endpoint}"
                )
            model_ddls.append(
                f"CREATE MODEL {m_name}\n"
                "INPUT(\n"
                "  content STRING(MAX),\n"
                "  task_type STRING(MAX),\n"
                ")\n"
                "OUTPUT(\n"
                "  embeddings\n"
                "    STRUCT<\n"
                "      statistics STRUCT<truncated BOOL, token_count FLOAT64>,\n"
                "      values ARRAY<FLOAT64>>\n"
                ")\n"
                "REMOTE OPTIONS (\n"
                f"  endpoint = '{m_endpoint}'\n"
                ");"
            )

        parts = rendered.split("{% for model in models %}")
        prefix = parts[0]
        suffix = ""
        if len(parts) > 1 and "{% endfor %}" in parts[1]:
            suffix = parts[1].split("{% endfor %}", 1)[1]
        rendered = prefix + "\n" + "\n".join(model_ddls) + suffix

    return rendered


def parse_sql_to_statements(sql_content: str) -> list[str]:
    """Parses a SQL script string into a list of individual DDL statements.

    Filters out single-line comments starting with '--' so that semicolons inside
    comments do not interfere with splitting statements. Note: Tailored for
    canonical schema DDL statements delimited by semicolons.

    Args:
        sql_content: Full text content of a SQL file or script.

    Returns:
        List of cleaned, non-empty DDL statement strings.
    """
    clean_lines: list[str] = []
    for line in sql_content.splitlines():
        clean_line = line.split("--")[0]
        if clean_line.strip():
            clean_lines.append(clean_line.rstrip())
    clean_sql = "\n".join(clean_lines)

    statements: list[str] = []
    for s in clean_sql.split(";"):
        s_stripped = s.strip()
        if s_stripped:
            statements.append(s_stripped)
    return statements


def get_schema_dir() -> Path:
    """Resolves the directory containing the schema SQL files.

    Returns:
        Path to the schema directory containing schema.sql and schema_golden.sql.
    """
    return Path(__file__).resolve().parent.parent / "schema"


def generate_golden_schema_sql(project_id: str = "test-project") -> str:
    """Generates the cumulative golden schema SQL string from baseline schema.sql and all migrations.

    Args:
        project_id: GCP project ID used for model endpoint interpolation.

    Returns:
        Formatted golden schema SQL string with license header.
    """
    from unittest.mock import MagicMock

    from datacommons_db.clients.spanner_client import (
        ExecutionStatus,
        SpannerClient,
    )
    from datacommons_db.migrations.migration_runner import MigrationRunner

    schema_dir = get_schema_dir()
    schema_sql_path = schema_dir / "schema.sql"
    template_content = schema_sql_path.read_text(encoding="utf-8")

    rendered = render_schema_template(template_content, project_id=project_id)
    baseline_statements = parse_sql_to_statements(rendered)

    # Collect DDL statements from all forward migration scripts
    mock_client = MagicMock(spec=SpannerClient)
    mock_client.table_exists.return_value = False
    mig_statements: list[str] = []
    mock_client.execute_ddl.side_effect = lambda stmts: (
        mig_statements.extend(stmts),
        MagicMock(status=ExecutionStatus.SUCCESS),
    )[1]

    runner = MigrationRunner(mock_client)
    for migration in runner.migrations:
        migration.upgrade(mock_client)

    all_stmts = baseline_statements + [s.strip() for s in mig_statements if s.strip()]

    header = """-- Copyright 2026 Google LLC.
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

-- ============================================================================
-- ⛔ AUTOGENERATED FILE - DO NOT EDIT DIRECTLY!
-- ============================================================================
-- This golden schema represents the cumulative Cloud Spanner schema generated
-- by applying schema.sql followed by all forward migration scripts up to HEAD.
--
-- To update this file when adding or editing migrations:
--   uv run python scripts/update_schema_golden.py
-- ============================================================================
"""
    return header + "\n" + ";\n\n".join(all_stmts) + ";\n"
