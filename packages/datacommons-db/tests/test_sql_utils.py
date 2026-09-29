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

from datacommons_db.utils.sql_utils import (
    parse_sql_to_statements,
    render_schema_template,
)


def test_parse_sql_to_statements_basic():
    sql = """
    -- Comment line
    CREATE TABLE Foo (id INT64) PRIMARY KEY (id);
    -- Another comment
    CREATE TABLE Bar (name STRING(64)) PRIMARY KEY (name);
    """
    stmts = parse_sql_to_statements(sql)
    assert len(stmts) == 2
    assert stmts[0] == "CREATE TABLE Foo (id INT64) PRIMARY KEY (id)"
    assert stmts[1] == "CREATE TABLE Bar (name STRING(64)) PRIMARY KEY (name)"


def test_parse_sql_to_statements_empty():
    assert parse_sql_to_statements("") == []
    assert parse_sql_to_statements("-- only comments\n-- here too") == []
    assert parse_sql_to_statements("   ; ;  \n") == []


def test_parse_sql_to_statements_with_inline_comments():
    sql = "CREATE TABLE Baz (id INT64) PRIMARY KEY (id); -- inline comment\n"
    stmts = parse_sql_to_statements(sql)
    assert len(stmts) == 1
    assert stmts[0] == "CREATE TABLE Baz (id INT64) PRIMARY KEY (id)"


def test_render_schema_template():
    template = """
    CREATE TABLE NodeEmbedding (id INT64);
    CREATE MODEL NodeEmbeddingModel REMOTE OPTIONS (
      endpoint = '//aiplatform.googleapis.com/projects/{project_id}/locations/{region}/publishers/google/models/text-embedding-005'
    );
    """
    rendered = render_schema_template(
        template,
        project_id="my-gcp-project",
        region="europe-west1",
    )
    assert "projects/my-gcp-project/locations/europe-west1" in rendered
    assert "{project_id}" not in rendered
    assert "{region}" not in rendered
