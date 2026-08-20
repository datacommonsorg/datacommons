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

"""Unit tests for pure Python migration utilities (tools/migrations/manage_migrations_utils.py)."""

import ast
import datetime
from pathlib import Path

import pytest

from tools.migrations import manage_migrations_utils

# ==============================================================================
# Helper Unit Tests (manage_migrations_utils)
# ==============================================================================


def test_sanitize_name_valid() -> None:
    assert manage_migrations_utils.sanitize_name("add_node_tables") == "add_node_tables"
    assert manage_migrations_utils.sanitize_name("add_table_1") == "add_table_1"


def test_sanitize_name_cleans_hyphens_spaces_and_casing() -> None:
    assert manage_migrations_utils.sanitize_name("Add Node-Tables") == "add_node_tables"
    assert (
        manage_migrations_utils.sanitize_name("  create  user_profile  ")
        == "create_user_profile"
    )
    assert (
        manage_migrations_utils.sanitize_name("--add___custom__index--")
        == "add_custom_index"
    )


def test_sanitize_name_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Migration name cannot be empty"):
        manage_migrations_utils.sanitize_name("")

    with pytest.raises(ValueError, match="Migration name cannot be empty"):
        manage_migrations_utils.sanitize_name("   ---   ")

    with pytest.raises(ValueError, match="Invalid migration name"):
        manage_migrations_utils.sanitize_name("add_node@table!")


def test_generate_utc_timestamps_explicit_datetime() -> None:
    dt = datetime.datetime(2026, 8, 19, 13, 54, 12, tzinfo=datetime.UTC)
    prefix, iso = manage_migrations_utils.generate_utc_timestamps(dt)
    assert prefix == "20260819135412"
    assert iso == "2026-08-19T13:54:12Z"


def test_generate_utc_timestamps_default_now() -> None:
    prefix, iso = manage_migrations_utils.generate_utc_timestamps()
    assert len(prefix) == 14
    assert prefix.isdigit()
    assert manage_migrations_utils.ISO_8601_UTC_PATTERN.match(iso)


def test_generate_migration_content_valid_ast() -> None:
    content = manage_migrations_utils.generate_migration_content(
        description="Add User table",
        creation_timestamp="2026-08-19T13:54:12Z",
    )
    parsed = ast.parse(content)
    assert parsed is not None

    assert f"description: str = {repr('Add User table')}" in content
    assert 'creation_timestamp: str = "2026-08-19T13:54:12Z"' in content
    assert "class Migration(SchemaMigration):" in content
    assert "def upgrade(self, spanner_client: SpannerClient) -> None:" in content


def test_escape_docstring_plain_text() -> None:
    assert (
        manage_migrations_utils.escape_docstring("Simple description")
        == "Simple description"
    )


def test_escape_docstring_triple_quotes() -> None:
    assert (
        manage_migrations_utils.escape_docstring('Contains """ quotes')
        == r"Contains \"\"\" quotes"
    )


def test_escape_docstring_trailing_quote() -> None:
    assert (
        manage_migrations_utils.escape_docstring('Ends with quote "')
        == r"Ends with quote \""
    )


def test_escape_docstring_backslashes() -> None:
    assert (
        manage_migrations_utils.escape_docstring(r"Path \to\file") == r"Path \\to\\file"
    )


def test_generate_migration_content_handles_quotes_and_special_chars() -> None:
    desc = r'Add "User" & \'Group\' table with \ path and """ triple quotes'
    content = manage_migrations_utils.generate_migration_content(
        description=desc,
        creation_timestamp="2026-08-19T13:54:12Z",
    )
    parsed = ast.parse(content)
    assert parsed is not None
    assert f"description: str = {repr(desc)}" in content


def test_create_migration_file_success(tmp_path: Path) -> None:
    dt = datetime.datetime(2026, 8, 19, 12, 0, 0, tzinfo=datetime.UTC)
    file_path, iso_ts, desc = manage_migrations_utils.create_migration_file(
        name="add_user",
        description="Add User Table",
        migrations_dir=tmp_path,
        target_dt=dt,
    )

    assert file_path.exists()
    assert file_path.name == "20260819120000_add_user.py"
    assert iso_ts == "2026-08-19T12:00:00Z"
    assert desc == "Add User Table"

    content = file_path.read_text()
    assert 'creation_timestamp: str = "2026-08-19T12:00:00Z"' in content
    ast.parse(content)


def test_create_migration_file_duplicate_raises(tmp_path: Path) -> None:
    dt = datetime.datetime(2026, 8, 19, 12, 0, 0, tzinfo=datetime.UTC)
    manage_migrations_utils.create_migration_file(
        name="add_user",
        migrations_dir=tmp_path,
        target_dt=dt,
    )

    with pytest.raises(FileExistsError, match="already exists"):
        manage_migrations_utils.create_migration_file(
            name="add_user",
            migrations_dir=tmp_path,
            target_dt=dt,
        )


# ==============================================================================
# find_migration_file Tests
# ==============================================================================


def test_find_migration_file_by_change_name(tmp_path: Path) -> None:
    mig1 = tmp_path / "20260817000000_bootstrap.py"
    mig1.write_text("class Migration: pass")
    mig2 = tmp_path / "20260818120000_add_node.py"
    mig2.write_text("class Migration: pass")

    found = manage_migrations_utils.find_migration_file("bootstrap", tmp_path)
    assert found == mig1

    found2 = manage_migrations_utils.find_migration_file("add_node", tmp_path)
    assert found2 == mig2


def test_find_migration_file_by_prefix_or_filename(tmp_path: Path) -> None:
    mig1 = tmp_path / "20260817000000_bootstrap.py"
    mig1.write_text("class Migration: pass")

    # By 14-digit prefix
    assert (
        manage_migrations_utils.find_migration_file("20260817000000", tmp_path) == mig1
    )
    # By filename
    assert (
        manage_migrations_utils.find_migration_file(
            "20260817000000_bootstrap.py", tmp_path
        )
        == mig1
    )
    # By stem
    assert (
        manage_migrations_utils.find_migration_file(
            "20260817000000_bootstrap", tmp_path
        )
        == mig1
    )
    # By Path object directly
    assert manage_migrations_utils.find_migration_file(mig1, tmp_path) == mig1
    # By relative Path within directory
    assert (
        manage_migrations_utils.find_migration_file(
            Path("20260817000000_bootstrap.py"), tmp_path
        )
        == mig1
    )


def test_find_migration_file_lenient_matching(tmp_path: Path) -> None:
    mig = tmp_path / "20260818120000_test_migration.py"
    mig.write_text("class Migration: pass")

    # Match with spaces
    assert (
        manage_migrations_utils.find_migration_file("test migration", tmp_path) == mig
    )
    # Match with hyphens
    assert (
        manage_migrations_utils.find_migration_file("test-migration", tmp_path) == mig
    )
    # Match with mixed casing
    assert (
        manage_migrations_utils.find_migration_file("Test Migration", tmp_path) == mig
    )


def test_find_migration_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(
        FileNotFoundError, match="No migration script found matching 'missing'"
    ):
        manage_migrations_utils.find_migration_file("missing", tmp_path)


def test_find_migration_file_ambiguous_raises(tmp_path: Path) -> None:
    (tmp_path / "20260817000000_add_node.py").write_text("class Migration: pass")
    (tmp_path / "20260818000000_add_node.py").write_text("class Migration: pass")

    with pytest.raises(ValueError, match="Ambiguous target 'add_node'"):
        manage_migrations_utils.find_migration_file("add_node", tmp_path)


# ==============================================================================
# update_migration_file Tests
# ==============================================================================


def test_update_migration_file_success(tmp_path: Path) -> None:
    file_path = tmp_path / "20260817000000_my_change.py"
    file_path.write_text(
        manage_migrations_utils.generate_migration_content(
            "My Change", "2026-08-17T00:00:00Z"
        )
    )

    dt = datetime.datetime(2026, 8, 19, 16, 30, 0, tzinfo=datetime.UTC)
    old_path, new_path, new_iso = manage_migrations_utils.update_migration_file(
        target=file_path,
        migrations_dir=tmp_path,
        target_dt=dt,
    )

    assert not file_path.exists()
    assert new_path.exists()
    assert new_path.name == "20260819163000_my_change.py"
    assert new_iso == "2026-08-19T16:30:00Z"

    content = new_path.read_text()
    assert 'creation_timestamp: str = "2026-08-19T16:30:00Z"' in content
    ast.parse(content)


def test_update_migration_file_missing_attribute_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "20260817000000_bad.py"
    file_path.write_text("class Migration: pass\n")

    with pytest.raises(
        ValueError, match="Could not find 'creation_timestamp' attribute"
    ):
        manage_migrations_utils.update_migration_file(
            target=file_path,
            migrations_dir=tmp_path,
        )


def test_discover_migrations(tmp_path: Path) -> None:
    (tmp_path / "20260817000000_bootstrap.py").write_text(
        manage_migrations_utils.generate_migration_content(
            "Bootstrap schema", "2026-08-17T00:00:00Z"
        )
    )
    (tmp_path / "20260818120000_add_node.py").write_text(
        manage_migrations_utils.generate_migration_content(
            "Add Node table", "2026-08-18T12:00:00Z"
        )
    )

    discovered = manage_migrations_utils.discover_migrations(tmp_path)
    assert len(discovered) == 2
    assert discovered[0].index == 1
    assert discovered[0].prefix_timestamp == "20260817000000"
    assert discovered[0].creation_timestamp == "2026-08-17T00:00:00Z"
    assert discovered[0].filename == "20260817000000_bootstrap.py"
    assert discovered[0].description == "Bootstrap schema"

    assert discovered[1].index == 2
    assert discovered[1].prefix_timestamp == "20260818120000"
    assert discovered[1].creation_timestamp == "2026-08-18T12:00:00Z"
    assert discovered[1].filename == "20260818120000_add_node.py"
    assert discovered[1].description == "Add Node table"


def test_discover_migrations_empty_or_missing_dir(tmp_path: Path) -> None:
    assert manage_migrations_utils.discover_migrations(tmp_path) == []
    assert manage_migrations_utils.discover_migrations(tmp_path / "nonexistent") == []
