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

"""Schema loader module for discovering, rendering, and parsing Cloud Spanner schema files."""

import importlib.resources
from pathlib import Path

from datacommons_db.utils.sql_utils import (
    parse_sql_to_statements,
    render_schema_template,
)

BASELINE_SCHEMA_FILENAME = "baseline_schema.sql"


def get_baseline_schema_path() -> Path:
    """Returns the filesystem path to the canonical baseline schema file.

    Returns:
        Path to baseline_schema.sql.

    Raises:
        FileNotFoundError: If the baseline schema file cannot be located.
    """
    try:
        package_files = importlib.resources.files("datacommons_db.schema")
        resource_path = package_files.joinpath(BASELINE_SCHEMA_FILENAME)
        path = Path(str(resource_path))
        if path.exists():
            return path
    except (
        TypeError,
        FileNotFoundError,
        ModuleNotFoundError,
        AttributeError,
        ValueError,
    ):
        pass

    local_path = Path(__file__).resolve().parent / BASELINE_SCHEMA_FILENAME
    if local_path.exists():
        return local_path

    raise FileNotFoundError(
        f"Baseline schema file '{BASELINE_SCHEMA_FILENAME}' not found in datacommons_db.schema"
    )


def load_baseline_template() -> str:
    """Reads the raw baseline schema SQL template.

    Returns:
        Raw SQL template string with placeholders.
    """
    return get_baseline_schema_path().read_text(encoding="utf-8")


def load_baseline_statements(
    *,
    project_id: str,
    region: str,
) -> list[str]:
    """Loads, renders placeholders, and splits the baseline schema into DDL statements.

    Args:
        project_id: GCP project ID hosting the Vertex AI endpoint or Spanner resources.
        region: GCP region hosting the Vertex AI endpoint or Spanner database.

    Returns:
        List of individual cleaned DDL statement strings ready for Spanner execution.
    """
    template_sql = load_baseline_template()
    rendered_sql = render_schema_template(
        template_sql,
        project_id=project_id,
        region=region,
    )
    return parse_sql_to_statements(rendered_sql)


# Backwards compatibility alias
class SchemaLoader:
    """Namespace alias for backward compatibility."""

    get_baseline_schema_path = staticmethod(get_baseline_schema_path)
    load_baseline_template = staticmethod(load_baseline_template)
    load_baseline_statements = staticmethod(load_baseline_statements)
