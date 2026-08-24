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

"""Validation utility functions and regex patterns for resource identifiers."""

import re

TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
RESOURCE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def validate_resource_id(name: str, value: object) -> None:
    """Validate that a GCP / Spanner resource ID matches expected identifier patterns.

    Args:
        name: The name of the resource parameter (e.g. 'project_id', 'instance_id').
        value: The value to validate.

    Raises:
        ValueError: If value is not a valid non-empty alphanumeric identifier.
    """
    if not isinstance(value, str) or not value or not RESOURCE_ID_PATTERN.match(value):
        raise ValueError(
            f"Invalid {name} '{value}'. Must be a non-empty string containing only alphanumeric characters, underscores, and hyphens."
        )


def validate_table_name(table_name: object) -> None:
    """Validate that a table name matches expected identifier patterns.

    Args:
        table_name: The table name to validate.

    Raises:
        ValueError: If table_name is not a valid identifier.
    """
    if (
        not isinstance(table_name, str)
        or not table_name
        or not TABLE_NAME_PATTERN.match(table_name)
    ):
        raise ValueError(
            f"Invalid table name '{table_name}'. Table names must match {TABLE_NAME_PATTERN.pattern}"
        )
