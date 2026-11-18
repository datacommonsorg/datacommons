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

"""Unit tests for datacommons_devtools.migrations.snapshot utilities."""

from pathlib import Path

import pytest
from datacommons_devtools.migrations.snapshot import (
    get_schema_snapshot_path,
    write_compiled_schema,
)


def test_get_schema_snapshot_path_resolves_to_datacommons_db() -> None:
    """Verifies get_schema_snapshot_path targets packages/datacommons-db/tests/snapshots/schema_snapshot.sql."""
    path = get_schema_snapshot_path()
    assert path.name == "schema_snapshot.sql"
    assert "datacommons-db" in str(path)
    assert path.parent.name == "snapshots"


def test_write_compiled_schema_to_custom_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies write_compiled_schema correctly writes to an explicit destination path."""
    custom_path = tmp_path / "subdir" / "snapshot.sql"
    monkeypatch.setattr(
        "datacommons_devtools.migrations.snapshot.generate_engine_schema_snapshot_sql",
        lambda **kwargs: "-- TEST COMPILED SCHEMA\nCREATE TABLE Node;\n",
    )

    written_path = write_compiled_schema(
        target_path=custom_path,
        project_id="custom-project",
        region="europe-west1",
    )

    assert written_path == custom_path
    assert custom_path.exists()
    content = custom_path.read_text(encoding="utf-8")
    assert "TEST COMPILED SCHEMA" in content
    assert "CREATE TABLE Node" in content
