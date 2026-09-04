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

import pytest
from datacommons_db.utils.validators import (
    validate_resource_id,
    validate_table_name,
)


@pytest.mark.parametrize(
    ("name", "val"),
    [
        ("project_id", "my-project-123"),
        ("instance_id", "spanner_inst-01"),
        ("database_id", "db_1"),
    ],
)
def test_validate_resource_id_valid(name: str, val: str):
    validate_resource_id(name, val)


@pytest.mark.parametrize(
    ("name", "val"),
    [
        ("project_id", ""),
        ("project_id", "   "),
        ("project_id", "proj with spaces"),
        ("project_id", "proj/slash"),
        ("project_id", "proj$invalid"),
        ("project_id", None),
        ("project_id", 123),
    ],
)
def test_validate_resource_id_invalid(name: str, val: object):
    with pytest.raises(ValueError, match="Invalid project_id"):
        validate_resource_id(name, val)


@pytest.mark.parametrize(
    "name",
    [
        "Node",
        "Edge",
        "custom_table_123",
        "SchemaMigrations",
    ],
)
def test_validate_table_name_valid(name: str):
    validate_table_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "Table with spaces",
        "Table;DROP TABLE users;--",
        "Table-With-Dashes",
        "Table$Name",
        None,
        123,
    ],
)
def test_validate_table_name_invalid(name: object):
    with pytest.raises(ValueError, match="Invalid table name"):
        validate_table_name(name)
