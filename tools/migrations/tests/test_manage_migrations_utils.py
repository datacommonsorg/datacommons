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
import json
from pathlib import Path

import pytest

from tools.migrations import manage_migrations_utils

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
    )
    deeply_nested_file.parent.mkdir(parents=True)
    monkeypatch.setattr(manage_migrations_utils, "__file__", str(deeply_nested_file))

    resolved = manage_migrations_utils.get_default_migrations_dir()
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
    )
    site_packages_file.parent.mkdir(parents=True)
    monkeypatch.setattr(manage_migrations_utils, "__file__", str(site_packages_file))
    monkeypatch.setattr(Path, "cwd", lambda: fake_repo_root / "tools")

    resolved = manage_migrations_utils.get_default_migrations_dir()
    assert resolved == local_scripts


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

    assert f"description: str = {json.dumps('Add User table')}" in content
    assert 'creation_timestamp: str = "2026-08-19T13:54:12Z"' in content
    assert "class Migration(SchemaMigration):" in content
    assert "def upgrade(self, spanner_client: SpannerClient) -> None:" in content


def test_generate_migration_content_escaping() -> None:
    """Verifies special characters and quotes in descriptions are safely escaped."""
    desc = 'Add "Special" Table with \'Quotes\' & \n Newlines and triple """ quotes'
    content = manage_migrations_utils.generate_migration_content(
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
        name="create_entities_table",
        description="Create entities table with indexes",
        migrations_dir=tmp_path,
    )

    assert target_file.exists()
    assert target_file.is_file()
    assert desc == "Create entities table with indexes"
    assert manage_migrations_utils.ISO_8601_UTC_PATTERN.match(iso_ts)

    match = manage_migrations_utils.FILENAME_PATTERN.match(target_file.name)
    assert match is not None
    assert match.group(2) == "create_entities_table"

    content = target_file.read_text(encoding="utf-8")
    assert f"description: str = {json.dumps(desc)}" in content
    assert f'creation_timestamp: str = "{iso_ts}"' in content


def test_create_migration_file_explicit_timestamp(tmp_path: Path) -> None:
    """Verifies creating a file with explicit datetime."""
    dt = datetime.datetime(2026, 8, 19, 10, 0, 0, tzinfo=datetime.UTC)
    target_file, iso_ts, desc = manage_migrations_utils.create_migration_file(
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
        name="duplicate_table",
        migrations_dir=tmp_path,
        target_dt=dt,
    )

    with pytest.raises(FileExistsError, match="already exists"):
        manage_migrations_utils.create_migration_file(
            name="duplicate_table",
            migrations_dir=tmp_path,
            target_dt=dt,
        )


def test_create_migration_file_invalid_name_raises(tmp_path: Path) -> None:
    """Verifies invalid name raises ValueError and does not create file on disk."""
    with pytest.raises(ValueError, match="Invalid migration name"):
        manage_migrations_utils.create_migration_file(
            name="invalid$name",
            migrations_dir=tmp_path,
        )
    assert len(list(tmp_path.glob("*.py"))) == 0
