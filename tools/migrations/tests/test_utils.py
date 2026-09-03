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
"""Unit tests for pure Python migration utilities (tools/migrations/utils.py)."""

import ast
import datetime
import json
from pathlib import Path

import pytest

from tools.migrations import manage_migrations_utils
from tools.migrations import utils

# ==============================================================================
# 0. get_default_migrations_dir Tests
# ==============================================================================


def test_get_default_migrations_dir_finds_nested_file_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies that upward search finds migrations dir even if utils file is deeply nested."""
    fake_repo_root = tmp_path / "repo"
    local_scripts = (
        fake_repo_root
        / "packages"
        / "datacommons-db"
        / "datacommons_db"
        / "migrations"
        / "migration_scripts"
    )
    local_scripts.mkdir(parents=True)

    deeply_nested_file = (
        fake_repo_root / "tools" / "deep" / "sub" / "pkg" / "manage_migrations_utils.py"
        fake_repo_root / "tools" / "deep" / "sub" / "pkg" / "utils.py"
    )
    deeply_nested_file.parent.mkdir(parents=True)
    monkeypatch.setattr(manage_migrations_utils, "__file__", str(deeply_nested_file))
    monkeypatch.setattr(utils, "__file__", str(deeply_nested_file))

    resolved = manage_migrations_utils.get_default_migrations_dir()
    resolved = utils.get_default_migrations_dir()
    assert resolved == local_scripts


def test_get_default_migrations_dir_finds_from_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies that upward search finds migrations dir from current working directory if file is in site-packages."""
    fake_repo_root = tmp_path / "repo"
    local_scripts = (
        fake_repo_root
        / "packages"
        / "datacommons-db"
        / "datacommons_db"
        / "migrations"
        / "migration_scripts"
    )
    local_scripts.mkdir(parents=True)

    site_packages_file = (
        tmp_path
        / "venv"
        / "lib"
        / "python3.11"
        / "site-packages"
        / "tools"
        / "manage_migrations_utils.py"
        / "utils.py"
    )
    site_packages_file.parent.mkdir(parents=True)
    monkeypatch.setattr(manage_migrations_utils, "__file__", str(site_packages_file))
    monkeypatch.setattr(utils, "__file__", str(site_packages_file))
    monkeypatch.setattr(Path, "cwd", lambda: fake_repo_root / "tools")

    resolved = manage_migrations_utils.get_default_migrations_dir()
    resolved = utils.get_default_migrations_dir()
    assert resolved == local_scripts


# ==============================================================================
# 1. sanitize_name Tests
# ==============================================================================


def test_sanitize_name_valid() -> None:
    """Verifies valid snake_case names pass through unchanged."""
    assert manage_migrations_utils.sanitize_name("add_node_tables") == "add_node_tables"
    assert manage_migrations_utils.sanitize_name("add_table_1") == "add_table_1"
    assert utils.sanitize_name("add_node_tables") == "add_node_tables"
    assert utils.sanitize_name("add_table_1") == "add_table_1"


def test_sanitize_name_cleans_hyphens_spaces_and_casing() -> None:
    """Verifies spaces, hyphens, uppercase letters, and duplicate underscores are cleaned."""
    assert manage_migrations_utils.sanitize_name("Add Node-Tables") == "add_node_tables"
    assert utils.sanitize_name("Add Node-Tables") == "add_node_tables"
    assert (
        manage_migrations_utils.sanitize_name("  create  user_profile  ")
        utils.sanitize_name("  create  user_profile  ")
        == "create_user_profile"
    )
    assert (
        manage_migrations_utils.sanitize_name("--add___custom__index--")
        utils.sanitize_name("--add___custom__index--")
        == "add_custom_index"
    )


def test_sanitize_name_invalid_raises() -> None:
    """Verifies empty strings or strings with invalid characters raise ValueError."""
    with pytest.raises(ValueError, match="Migration name cannot be empty"):
        manage_migrations_utils.sanitize_name("")
        utils.sanitize_name("")

    with pytest.raises(ValueError, match="Migration name cannot be empty"):
        manage_migrations_utils.sanitize_name("   ---   ")
        utils.sanitize_name("   ---   ")

    with pytest.raises(ValueError, match="Invalid migration name"):
        manage_migrations_utils.sanitize_name("add_node@table!")
        utils.sanitize_name("add_node@table!")


# ==============================================================================
# 2. generate_utc_timestamps Tests
# ==============================================================================


def test_generate_utc_timestamps_explicit_datetime() -> None:
    """Verifies prefix and ISO timestamp generation with explicit UTC datetime."""
    dt = datetime.datetime(2026, 8, 19, 13, 54, 12, tzinfo=datetime.UTC)
    prefix, iso = manage_migrations_utils.generate_utc_timestamps(dt)
    prefix, iso = utils.generate_utc_timestamps(dt)
    assert prefix == "20260819135412"
    assert iso == "2026-08-19T13:54:12Z"


def test_generate_utc_timestamps_default_now() -> None:
    """Verifies default datetime generation produces 14-digit prefix and valid ISO timestamp."""
    prefix, iso = manage_migrations_utils.generate_utc_timestamps()
    prefix, iso = utils.generate_utc_timestamps()
    assert len(prefix) == 14
    assert prefix.isdigit()
    assert manage_migrations_utils.ISO_8601_UTC_PATTERN.match(iso)
    assert utils.ISO_8601_UTC_PATTERN.match(iso)


# ==============================================================================
# 3. Template Generation Tests
# ==============================================================================


def test_generate_migration_content_valid_ast() -> None:
    """Verifies generated boilerplate content parses as valid Python AST."""
    content = manage_migrations_utils.generate_migration_content(
    content = utils.generate_migration_content(
        description="Add User table",
        creation_timestamp="2026-08-19T13:54:12Z",
    )
    parsed = ast.parse(content)
    assert parsed is not None

    assert f"description: str = {json.dumps('Add User table')}" in content
    assert 'creation_timestamp: str = "2026-08-19T13:54:12Z"' in content
    assert "class Migration(SchemaMigration):" in content
    assert "def upgrade(self, spanner_client: SpannerClient) -> None:" in content


def test_generate_migration_content_escaping() -> None:
    """Verifies special characters and quotes in descriptions are safely escaped."""
    desc = 'Add "Special" Table with \'Quotes\' & \n Newlines and triple """ quotes'
    content = manage_migrations_utils.generate_migration_content(
    content = utils.generate_migration_content(
        description=desc,
        creation_timestamp="2026-08-19T13:54:12Z",
    )
    parsed = ast.parse(content)
    assert parsed is not None
    assert f"description: str = {json.dumps(desc)}" in content


# ==============================================================================
# 4. create_migration_file Tests
# ==============================================================================


def test_create_migration_file_success(tmp_path: Path) -> None:
    """Verifies creating a new migration file generates expected file on disk."""
    target_file, iso_ts, desc = manage_migrations_utils.create_migration_file(
    target_file, iso_ts, desc = utils.create_migration_file(
        name="create_entities_table",
        description="Create entities table with indexes",
        migrations_dir=tmp_path,
    )

    assert target_file.exists()
    assert target_file.is_file()
    assert desc == "Create entities table with indexes"
    assert manage_migrations_utils.ISO_8601_UTC_PATTERN.match(iso_ts)
    assert utils.ISO_8601_UTC_PATTERN.match(iso_ts)

    match = manage_migrations_utils.FILENAME_PATTERN.match(target_file.name)
    match = utils.FILENAME_PATTERN.match(target_file.name)
    assert match is not None
    assert match.group(2) == "create_entities_table"

    content = target_file.read_text(encoding="utf-8")
    assert f"description: str = {json.dumps(desc)}" in content
    assert f'creation_timestamp: str = "{iso_ts}"' in content


def test_create_migration_file_explicit_timestamp(tmp_path: Path) -> None:
    """Verifies creating a file with explicit datetime."""
    dt = datetime.datetime(2026, 8, 19, 10, 0, 0, tzinfo=datetime.UTC)
    target_file, iso_ts, desc = manage_migrations_utils.create_migration_file(
    target_file, iso_ts, desc = utils.create_migration_file(
        name="explicit_ts_migration",
        migrations_dir=tmp_path,
        target_dt=dt,
    )

    assert target_file.name == "20260819100000_explicit_ts_migration.py"
    assert iso_ts == "2026-08-19T10:00:00Z"
    assert desc == "Explicit ts migration"


def test_create_migration_file_existing_raises(tmp_path: Path) -> None:
    """Verifies attempting to create a duplicate migration with identical timestamp raises FileExistsError."""
    dt = datetime.datetime(2026, 8, 19, 10, 0, 0, tzinfo=datetime.UTC)
    manage_migrations_utils.create_migration_file(
    utils.create_migration_file(
        name="duplicate_table",
        migrations_dir=tmp_path,
        target_dt=dt,
    )

    with pytest.raises(FileExistsError, match="already exists"):
        manage_migrations_utils.create_migration_file(
        utils.create_migration_file(
            name="duplicate_table",
            migrations_dir=tmp_path,
            target_dt=dt,
        )


def test_create_migration_file_invalid_name_raises(tmp_path: Path) -> None:
    """Verifies invalid name raises ValueError and does not create file on disk."""
    with pytest.raises(ValueError, match="Invalid migration name"):
        manage_migrations_utils.create_migration_file(
        utils.create_migration_file(
            name="invalid$name",
            migrations_dir=tmp_path,
        )
    assert len(list(tmp_path.glob("*.py"))) == 0


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
    found = utils.find_migration_file("bootstrap", tmp_path)
    assert found == mig1

    found2 = manage_migrations_utils.find_migration_file("add_node", tmp_path)
    found2 = utils.find_migration_file("add_node", tmp_path)
    assert found2 == mig2


def test_find_migration_file_by_prefix_or_filename(tmp_path: Path) -> None:
    """Verifies locating migration files by 14-digit prefix, filename, stem, or Path object."""
    mig1 = tmp_path / "20260817000000_bootstrap.py"
    mig1.write_text("class Migration: pass")

    # By 14-digit prefix
    assert (
        manage_migrations_utils.find_migration_file("20260817000000", tmp_path) == mig1
        utils.find_migration_file("20260817000000", tmp_path) == mig1
    )
    # By filename
    assert (
        manage_migrations_utils.find_migration_file(
        utils.find_migration_file(
            "20260817000000_bootstrap.py", tmp_path
        )
        == mig1
    )
    # By stem
    assert (
        manage_migrations_utils.find_migration_file(
        utils.find_migration_file(
            "20260817000000_bootstrap", tmp_path
        )
        == mig1
    )
    # By Path object directly
    assert manage_migrations_utils.find_migration_file(mig1, tmp_path) == mig1
    assert utils.find_migration_file(mig1, tmp_path) == mig1
    # By relative Path within directory
    assert (
        manage_migrations_utils.find_migration_file(
        utils.find_migration_file(
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
        utils.find_migration_file("test migration", tmp_path) == mig
    )
    # Match with hyphens
    assert (
        manage_migrations_utils.find_migration_file("test-migration", tmp_path) == mig
        utils.find_migration_file("test-migration", tmp_path) == mig
    )
    # Match with mixed casing
    assert (
        manage_migrations_utils.find_migration_file("Test Migration", tmp_path) == mig
        utils.find_migration_file("Test Migration", tmp_path) == mig
    )


def test_find_migration_file_not_found(tmp_path: Path) -> None:
    """Verifies find_migration_file raises FileNotFoundError when no match is found."""
    with pytest.raises(
        FileNotFoundError, match="No migration script found matching 'missing'"
    ):
        manage_migrations_utils.find_migration_file("missing", tmp_path)
        utils.find_migration_file("missing", tmp_path)


def test_find_migration_file_ambiguous_raises(tmp_path: Path) -> None:
    """Verifies find_migration_file raises ValueError when target matches multiple files."""
    (tmp_path / "20260817000000_add_node.py").write_text("class Migration: pass")
    (tmp_path / "20260818000000_add_node.py").write_text("class Migration: pass")

    with pytest.raises(ValueError, match="Ambiguous target 'add_node'"):
        manage_migrations_utils.find_migration_file("add_node", tmp_path)
        utils.find_migration_file("add_node", tmp_path)


# ==============================================================================
# 6. update_migration_file Tests
# ==============================================================================


def test_update_migration_file_success(tmp_path: Path) -> None:
    """Verifies re-timestamping and renaming of an existing migration file."""
    file_path = tmp_path / "20260817000000_my_change.py"
    file_path.write_text(
        manage_migrations_utils.generate_migration_content(
        utils.generate_migration_content(
            "My Change", "2026-08-17T00:00:00Z"
        )
    )

    dt = datetime.datetime(2026, 8, 19, 16, 30, 0, tzinfo=datetime.UTC)
    old_path, new_path, new_iso = manage_migrations_utils.update_migration_file(
    old_path, new_path, new_iso = utils.update_migration_file(
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
    _, new_path, new_iso = utils.update_migration_file(
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
        utils.update_migration_file(
            target=bad_file,
            migrations_dir=tmp_path,
        )


def test_update_migration_file_target_exists_raises(tmp_path: Path) -> None:
    """Verifies that update_migration_file fails fast with FileExistsError if target filename already exists."""
    dt = datetime.datetime(2026, 8, 19, 12, 0, 0, tzinfo=datetime.UTC)
    source_file = tmp_path / "20260817000000_my_change.py"
    source_file.write_text(
        manage_migrations_utils.generate_migration_content(
        utils.generate_migration_content(
            "My Change", "2026-08-17T00:00:00Z"
        )
    )

    # Pre-create the target file that would collide
    collision_file = tmp_path / "20260819120000_my_change.py"
    collision_file.write_text("class Existing: pass\n")

    with pytest.raises(FileExistsError, match="Target migration file already exists"):
        manage_migrations_utils.update_migration_file(
        utils.update_migration_file(
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
        utils.update_migration_file(
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
        utils.update_migration_file(
            target=file_path,
            migrations_dir=tmp_path,
        )


def test_update_migration_file_ignores_other_classes_and_module_vars(
    tmp_path: Path,
) -> None:
    """Verifies update_migration_file targets SchemaMigration subclass and ignores other classes/variables."""
    file_path = tmp_path / "20260817000000_audit_table.py"
    initial_content = """# Copyright 2026 Google LLC.
from datacommons_db.migrations.base import SchemaMigration

creation_timestamp = "1999-01-01T00:00:00Z"

class OtherClass:
    creation_timestamp = "2000-01-01T00:00:00Z"

class Migration(SchemaMigration):
    description: str = "Audit table"
    creation_timestamp: str = "2026-08-17T00:00:00Z"

    def upgrade(self, spanner_client):
        pass
"""
    file_path.write_text(initial_content)

    dt = datetime.datetime(2026, 8, 20, 10, 0, 0, tzinfo=datetime.UTC)
    _, new_path, new_iso = manage_migrations_utils.update_migration_file(
    _, new_path, new_iso = utils.update_migration_file(
        target=file_path,
        migrations_dir=tmp_path,
        target_dt=dt,
    )

    updated = new_path.read_text()
    assert 'creation_timestamp = "1999-01-01T00:00:00Z"' in updated
    assert 'creation_timestamp = "2000-01-01T00:00:00Z"' in updated
    assert 'creation_timestamp: str = "2026-08-20T10:00:00Z"' in updated
