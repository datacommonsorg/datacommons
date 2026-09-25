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
    region: str = "us-central1",
) -> str:
    """Renders placeholders in the baseline schema template.

    Args:
        template_sql: The raw SQL template string containing {project_id} and {region}.
        project_id: GCP project ID hosting the Vertex AI endpoint.
        region: GCP region hosting the Vertex AI endpoint. Defaults to 'us-central1'.

    Returns:
        Rendered SQL script string ready for statement parsing.
    """
    return template_sql.replace("{project_id}", project_id).replace("{region}", region)


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
    """Resolves the directory containing the baseline schema SQL files.

    Returns:
        Path to the schema directory containing schema.sql.
    """
    return Path(__file__).resolve().parent.parent / "schema"
