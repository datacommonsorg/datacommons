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

"""Unit tests for datacommons_db.schema.loader.SchemaLoader."""

from unittest.mock import patch

import pytest
from datacommons_db.schema.loader import (
    BASELINE_SCHEMA_FILENAME,
    SchemaLoader,
    get_baseline_schema_path,
    load_baseline_statements,
    load_baseline_template,
)


def test_get_baseline_schema_path_exists():
    path = get_baseline_schema_path()
    assert path.exists()
    assert path.name == BASELINE_SCHEMA_FILENAME
    # Also verify backward compatible class method works
    assert SchemaLoader.get_baseline_schema_path() == path


def test_get_baseline_schema_path_not_found():
    with (
        patch(
            "importlib.resources.files", side_effect=TypeError("mock import failure")
        ),
        patch("pathlib.Path.exists", return_value=False),
        pytest.raises(FileNotFoundError, match="Baseline schema file"),
    ):
        get_baseline_schema_path()


def test_load_baseline_template():
    content = load_baseline_template()
    assert "CREATE TABLE Node" in content
    assert "CREATE TABLE Edge" in content


def test_load_baseline_statements():
    statements = load_baseline_statements(
        project_id="test-project",
        region="us-central1",
    )
    assert len(statements) > 0
    assert any("CREATE TABLE Node" in stmt for stmt in statements)
    assert any("CREATE TABLE Edge" in stmt for stmt in statements)
    for stmt in statements:
        assert "{project_id}" not in stmt
        assert "{region}" not in stmt
