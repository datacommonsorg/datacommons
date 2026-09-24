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

        prefix = rendered.split("{% for model in models %}")[0]
        rendered = prefix + "\n" + "\n".join(model_ddls)

    return rendered


def parse_sql_to_statements(sql_content: str) -> list[str]:
    """Parses a SQL script string into a list of individual DDL statements.

    Filters out single-line comments starting with '--' so that semicolons inside
    comments do not interfere with splitting statements.

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
