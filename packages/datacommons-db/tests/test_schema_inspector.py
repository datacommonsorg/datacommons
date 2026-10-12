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

"""Unit tests for datacommons_db.schema.inspector."""

from unittest.mock import MagicMock

from datacommons_db.schema.inspector import inspect_database_schema


def test_inspect_database_schema():
    mock_client = MagicMock()
    mock_client.database.name = "projects/test/instances/test/databases/test"
    mock_response = MagicMock()
    mock_response.statements = [
        "CREATE TABLE Node (id STRING(MAX)) PRIMARY KEY (id);",
        "CREATE TABLE Edge (src STRING(MAX)) PRIMARY KEY (src);",
    ]
    mock_client.client.database_admin_api.get_database_ddl.return_value = mock_response
    ddl = inspect_database_schema(mock_client)
    assert len(ddl) == 2
    assert "CREATE TABLE Node" in ddl[0]
