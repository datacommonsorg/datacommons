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
# 1. sanitize_name Tests
# ==============================================================================


def test_sanitize_name_valid() -> None:
    """Verifies valid snake_case names pass through unchanged."""
    assert manage_migrations_utils.sanitize_name("add_node_tables") == "add_node_tables"
    assert manage_migrations_utils.sanitize_name("add_table_1") == "add_table_1"


def test_sanitize_name_cleans_hyphens_spaces_and_casing() -> None:
    """Verifies spaces, hyphens, uppercase letters, and duplicate underscores are cleaned."""
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
    """Verifies empty strings or strings with invalid characters raise ValueError."""
    with pytest.raises(ValueError, match="Migration name cannot be empty"):
        manage_migrations_utils.sanitize_name("")

    with pytest.raises(ValueError, match="Migration name cannot be empty"):
        manage_migrations_utils.sanitize_name("   ---   ")

    with pytest.raises(ValueError, match="Invalid migration name"):
        manage_migrations_utils.sanitize_name("add_node@table!")


# ==============================================================================
# 2. generate_utc_timestamps Tests
# ==============================================================================


def test_generate_utc_timestamps_explicit_datetime() -> None:
    """Verifies prefix and ISO timestamp generation with explicit UTC datetime."""
    dt = datetime.datetime(2026, 8, 19, 13, 54, 12, tzinfo=datetime.UTC)
    prefix, iso = manage_migrations_utils.generate_utc_timestamps(dt)
    assert prefix == "20260819135412"
    assert iso == "2026-08-19T13:54:12Z"


def test_generate_utc_timestamps_default_now() -> None:
    """Verifies default datetime generation produces 14-digit prefix and valid ISO timestamp."""
    prefix, iso = manage_migrations_utils.generate_utc_timestamps()
    assert len(prefix) == 14
    assert prefix.isdigit()
    assert manage_migrations_utils.ISO_8601_UTC_PATTERN.match(iso)


# ==============================================================================
# 3. Template Generation Tests
# ==============================================================================


def test_generate_migration_content_valid_ast() -> None:
    """Verifies generated boilerplate content parses as valid Python AST."""
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


def test_generate_migration_content_handles_quotes_and_special_chars() -> None:
    """Verifies migration content generation handles complex quotes, backslashes, and characters."""
    test_descriptions = [
        r'Add "User" & \'Group\' table with \ path and """ triple quotes',
        'Ends with triple quotes """',
        'Ends with four quotes """" ',
        'Ends with quote "',
        'Ends with two quotes ""',
        r"Ends with backslash and quote \"",
    ]
    for desc in test_descriptions:
        content = manage_migrations_utils.generate_migration_content(
            description=desc,
            creation_timestamp="2026-08-19T13:54:12Z",
        )
        parsed = ast.parse(content)
        assert parsed is not None
        # Verify the description attribute extracted from AST exactly matches the original description
        cls_node = parsed.body[2]  # Migration class node
        desc_node = next(
            item
            for item in cls_node.body
            if isinstance(item, ast.AnnAssign) and item.target.id == "description"
        )
        assert desc_node.value.value == desc
        assert f"description: str = {repr(desc)}" in content


# ==============================================================================
# 4. create_migration_file Tests
# ==============================================================================


def test_create_migration_file_success(tmp_path: Path) -> None:
    """Verifies successful creation of migration file on disk with correct boilerplate."""
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
    """Verifies create_migration_file raises FileExistsError if target file already exists."""
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


def test_create_migration_file_syntax_error_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies create_migration_file validates AST syntax and raises ValueError on invalid syntax."""
    monkeypatch.setattr(
        manage_migrations_utils,
        "generate_migration_content",
        lambda desc, ts: "def invalid_python_syntax(:",
    )
    with pytest.raises(
        ValueError, match="Generated migration script has syntax errors"
    ):
        manage_migrations_utils.create_migration_file(
            name="broken_script",
            migrations_dir=tmp_path,
        )


# ==============================================================================
# 5. find_migration_file Tests
# ==============================================================================


def test_find_migration_file_by_change_name(tmp_path: Path) -> None:
    """Verifies locating migration files by change name identifier."""
    mig1 = tmp_path / "20260817000000_bootstrap.py"
    mig1.write_text("class Migration: pass")
    mig2 = tmp_path / "20260818120000_add_node.py"
    mig2.write_text("class Migration: pass")

    found = manage_migrations_utils.find_migration_file("bootstrap", tmp_path)
    assert found == mig1

    found2 = manage_migrations_utils.find_migration_file("add_node", tmp_path)
    assert found2 == mig2


def test_find_migration_file_by_prefix_or_filename(tmp_path: Path) -> None:
    """Verifies locating migration files by 14-digit prefix, filename, stem, or Path object."""
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
    """Verifies locating migration files with spaces, hyphens, and mixed casing."""
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
    """Verifies find_migration_file raises FileNotFoundError when no match is found."""
    with pytest.raises(
        FileNotFoundError, match="No migration script found matching 'missing'"
    ):
        manage_migrations_utils.find_migration_file("missing", tmp_path)


def test_find_migration_file_ambiguous_raises(tmp_path: Path) -> None:
    """Verifies find_migration_file raises ValueError when target matches multiple files."""
    (tmp_path / "20260817000000_add_node.py").write_text("class Migration: pass")
    (tmp_path / "20260818000000_add_node.py").write_text("class Migration: pass")

    with pytest.raises(ValueError, match="Ambiguous target 'add_node'"):
        manage_migrations_utils.find_migration_file("add_node", tmp_path)


# ==============================================================================
# 6. update_migration_file Tests
# ==============================================================================


def test_update_migration_file_success(tmp_path: Path) -> None:
    """Verifies re-timestamping and renaming of an existing migration file."""
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


def test_update_migration_file_only_updates_first_occurrence(tmp_path: Path) -> None:
    """Verifies update_migration_file AST replacement only updates class attribute and preserves comments/SQL."""
    file_path = tmp_path / "20260817000000_audit_table.py"
    initial_content = """# Copyright 2026 Google LLC.
# Top-of-file comment mentioning creation_timestamp = "1999-01-01T00:00:00Z"
from datacommons_db.migrations.base import SchemaMigration

class Migration(SchemaMigration):
    description: str = "Audit table"
    creation_timestamp: str = "2026-08-17T00:00:00Z"

    def upgrade(self, spanner_client):
        # SQL query mentioning creation_timestamp = "..."
        query = 'UPDATE Audit SET creation_timestamp = "2020-01-01T00:00:00Z"'
"""
    file_path.write_text(initial_content)

    dt = datetime.datetime(2026, 8, 20, 10, 0, 0, tzinfo=datetime.UTC)
    _, new_path, new_iso = manage_migrations_utils.update_migration_file(
        target=file_path,
        migrations_dir=tmp_path,
        target_dt=dt,
    )

    updated = new_path.read_text()
    # Header comment must be untouched
    assert (
        '# Top-of-file comment mentioning creation_timestamp = "1999-01-01T00:00:00Z"'
        in updated
    )
    # Class attribute must be updated
    assert 'creation_timestamp: str = "2026-08-20T10:00:00Z"' in updated
    # Second occurrence (inside upgrade method / SQL query) must NOT be modified
    assert 'UPDATE Audit SET creation_timestamp = "2020-01-01T00:00:00Z"' in updated


def test_update_migration_file_invalid_filename_raises(tmp_path: Path) -> None:
    """Verifies that updating a file not conforming to YYYYMMDDHHMMSS_<name>.py raises ValueError."""
    bad_file = tmp_path / "not_a_valid_migration.py"
    bad_file.write_text("class Migration: pass\n")

    with pytest.raises(ValueError, match="does not match expected convention"):
        manage_migrations_utils.update_migration_file(
            target=bad_file,
            migrations_dir=tmp_path,
        )


def test_update_migration_file_target_exists_raises(tmp_path: Path) -> None:
    """Verifies that update_migration_file fails fast with FileExistsError if target filename already exists."""
    dt = datetime.datetime(2026, 8, 19, 12, 0, 0, tzinfo=datetime.UTC)
    source_file = tmp_path / "20260817000000_my_change.py"
    source_file.write_text(
        manage_migrations_utils.generate_migration_content(
            "My Change", "2026-08-17T00:00:00Z"
        )
    )

    # Pre-create the target file that would collide
    collision_file = tmp_path / "20260819120000_my_change.py"
    collision_file.write_text("class Existing: pass\n")

    with pytest.raises(FileExistsError, match="Target migration file already exists"):
        manage_migrations_utils.update_migration_file(
            target=source_file,
            migrations_dir=tmp_path,
            target_dt=dt,
        )


def test_update_migration_file_missing_attribute_raises(tmp_path: Path) -> None:
    """Verifies update_migration_file raises ValueError if creation_timestamp attribute is missing."""
    file_path = tmp_path / "20260817000000_bad.py"
    file_path.write_text("class Migration: pass\n")

    with pytest.raises(
        ValueError, match="Could not find 'creation_timestamp' attribute"
    ):
        manage_migrations_utils.update_migration_file(
            target=file_path,
            migrations_dir=tmp_path,
        )


def test_update_migration_file_syntax_error_preflight_raises(tmp_path: Path) -> None:
    """Verifies update_migration_file validates target file syntax before modification and raises ValueError."""
    file_path = tmp_path / "20260817000000_broken.py"
    file_path.write_text(
        "class Migration:\n  creation_timestamp = '2026-08-17T00:00:00Z'\n  def (\n"
    )

    with pytest.raises(ValueError, match="has syntax errors"):
        manage_migrations_utils.update_migration_file(
            target=file_path,
            migrations_dir=tmp_path,
        )


# ==============================================================================
# 7. discover_migrations Tests
# ==============================================================================


def test_discover_migrations(tmp_path: Path) -> None:
    """Verifies discovering migration files sorted chronologically with extracted metadata."""
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


def test_discover_migrations_prefix_fallback_timestamp(tmp_path: Path) -> None:
    """Verifies that discover_migrations derives ISO timestamp from filename prefix if attribute is missing."""
    script_file = tmp_path / "20260817143025_legacy_migration.py"
    script_file.write_text(
        'description: str = "Legacy migration without explicit timestamp attribute"\n'
    )

    discovered = manage_migrations_utils.discover_migrations(tmp_path)
    assert len(discovered) == 1
    assert discovered[0].filename == "20260817143025_legacy_migration.py"
    assert discovered[0].prefix_timestamp == "20260817143025"
    assert discovered[0].creation_timestamp == "2026-08-17T14:30:25Z"
    assert (
        discovered[0].description
        == "Legacy migration without explicit timestamp attribute"
    )


def test_discover_migrations_syntax_error_handled(tmp_path: Path) -> None:
    """Verifies discover_migrations handles files with syntax errors gracefully without raising."""
    bad_script = tmp_path / "20260819150000_syntax_error.py"
    bad_script.write_text("class Migration:\n  def broken(\n")

    discovered = manage_migrations_utils.discover_migrations(tmp_path)
    assert len(discovered) == 1
    assert discovered[0].filename == "20260819150000_syntax_error.py"
    assert discovered[0].description.startswith("<syntax error:")


def test_discover_migrations_empty_or_missing_dir(tmp_path: Path) -> None:
    """Verifies discover_migrations returns empty list for empty or non-existent directory."""
    assert manage_migrations_utils.discover_migrations(tmp_path) == []
    assert manage_migrations_utils.discover_migrations(tmp_path / "nonexistent") == []
