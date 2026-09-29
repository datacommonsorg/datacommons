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

"""Schema inspection utilities for querying and comparing live Cloud Spanner / emulator DDL."""

import re
from typing import Any

from datacommons_db.clients import SpannerClient

_CREATE_TABLE_PATTERN = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_]+)",
    re.IGNORECASE,
)
_CREATE_MODEL_PATTERN = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?MODEL\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_]+)",
    re.IGNORECASE,
)


def inspect_database_schema(spanner_client: SpannerClient) -> list[str]:
    """Retrieves engine-materialized DDL statements from the active Cloud Spanner database or emulator.

    Uses the Spanner admin API `database_admin_api.get_database_ddl()` to inspect the live collapsed schema.

    Args:
        spanner_client: Connected SpannerClient instance.

    Returns:
        List of DDL statement strings representing the live database schema.
    """
    database_name = spanner_client.database.name
    response = spanner_client.client.database_admin_api.get_database_ddl(
        database=database_name
    )
    return list(response.statements)


def extract_table_names(ddl_statements: list[str]) -> list[str]:
    """Extracts table names from a list of DDL statement strings.

    Args:
        ddl_statements: Sequence of DDL strings (e.g. from get_schema_ddl or migration files).

    Returns:
        Sorted, deduplicated list of table names.
    """
    tables: set[str] = set()
    for stmt in ddl_statements:
        match = _CREATE_TABLE_PATTERN.search(stmt)
        if match:
            tables.add(match.group(1))
    return sorted(tables)


def extract_model_names(ddl_statements: list[str]) -> list[str]:
    """Extracts model names from a list of DDL statement strings.

    Args:
        ddl_statements: Sequence of DDL strings.

    Returns:
        Sorted, deduplicated list of model names.
    """
    models: set[str] = set()
    for stmt in ddl_statements:
        match = _CREATE_MODEL_PATTERN.search(stmt)
        if match:
            models.add(match.group(1))
    return sorted(models)


def compare_live_schema_to_compiled(
    spanner_client: SpannerClient,
    compiled_statements: list[str],
) -> dict[str, Any]:
    """Compares the live database schema against expected compiled migration DDL statements.

    Differentiates between tables and remote models, taking into account emulator
    limitations (e.g. remote Vertex AI models unsupported on Cloud Spanner emulator).

    Args:
        spanner_client: Connected SpannerClient instance.
        compiled_statements: List of DDL statements generated from compiled migrations.

    Returns:
        Dictionary summarizing table parity, model parity, and emulator status.
    """
    live_ddl = inspect_database_schema(spanner_client)

    live_tables = set(extract_table_names(live_ddl))
    expected_tables = set(extract_table_names(compiled_statements))

    live_models = set(extract_model_names(live_ddl))
    expected_models = set(extract_model_names(compiled_statements))

    return {
        "is_emulator": spanner_client.is_emulator,
        "matching_tables": sorted(live_tables & expected_tables),
        "missing_tables": sorted(expected_tables - live_tables),
        "extra_tables": sorted(live_tables - expected_tables),
        "matching_models": sorted(live_models & expected_models),
        "missing_models": sorted(expected_models - live_models),
    }
