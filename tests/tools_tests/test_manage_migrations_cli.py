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

"""CLI command tests for developer migration DevOps tooling (tools/migrations/manage_migrations_cli.py)."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from tools.migrations import manage_migrations_utils
from tools.migrations.manage_migrations_cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_migrations_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolates CLI tests to a temporary directory."""
    monkeypatch.setattr(
        "tools.migrations.manage_migrations_utils.DEFAULT_MIGRATIONS_DIR",
        tmp_path,
    )
    return tmp_path


# ==============================================================================
# 1. 'create' Command Tests
# ==============================================================================


def test_cli_create_command(runner: CliRunner, tmp_path: Path) -> None:
    """Verifies creating a new migration script with custom description."""
    result = runner.invoke(
        cli,
        [
            "create",
            "add_observations",
            "-d",
            "Add Observation table",
        ],
    )

    assert result.exit_code == 0
    assert "Successfully created migration script" in result.output

    created_files = list(tmp_path.glob("*.py"))
    assert len(created_files) == 1
    created_file = created_files[0]

    assert created_file.name.endswith("_add_observations.py")
    match = manage_migrations_utils.FILENAME_PATTERN.match(created_file.name)
    assert match is not None

    content = created_file.read_text()
    assert f"description: str = {repr('Add Observation table')}" in content
    assert "SchemaMigration" in content


def test_cli_create_command_default_description(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Verifies create command generates a default capitalized description if omitted."""
    result = runner.invoke(cli, ["create", "add_indexes"])

    assert result.exit_code == 0
    assert "Successfully created migration script" in result.output
    assert "Add indexes" in result.output

    created_files = list(tmp_path.glob("*_add_indexes.py"))
    assert len(created_files) == 1
    content = created_files[0].read_text()
    assert f"description: str = {repr('Add indexes')}" in content


def test_cli_create_command_invalid_name_raises(runner: CliRunner) -> None:
    """Verifies create command exits with an error for invalid migration names."""
    result = runner.invoke(cli, ["create", "invalid@name!"])
    assert result.exit_code != 0
    assert "Invalid migration name" in result.output


def test_cli_create_command_duplicate_raises(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies create command exits with an error if target file already exists."""
    monkeypatch.setattr(
        "tools.migrations.manage_migrations_utils.generate_utc_timestamps",
        lambda _target_dt=None: ("20260819120000", "2026-08-19T12:00:00Z"),
    )
    res1 = runner.invoke(cli, ["create", "add_table"])
    assert res1.exit_code == 0

    res2 = runner.invoke(cli, ["create", "add_table"])
    assert res2.exit_code != 0
    assert "already exists" in res2.output


# ==============================================================================
# 2. 'bump' Command Tests
# ==============================================================================


def test_cli_bump_command_confirmed(runner: CliRunner, tmp_path: Path) -> None:
    """Verifies bumping a migration script when user confirms interactive prompt."""
    file_path = tmp_path / "20260817000000_add_user.py"
    file_path.write_text(
        manage_migrations_utils.generate_migration_content(
            "Add User", "2026-08-17T00:00:00Z"
        )
    )

    result = runner.invoke(
        cli,
        ["bump", "add_user"],
        input="y\n",
    )

    assert result.exit_code == 0
    assert "Planned changes:" in result.output
    assert "Proceed with bump?" in result.output
    assert "Successfully bumped migration script" in result.output
    assert not file_path.exists()

    updated_files = list(tmp_path.glob("*.py"))
    assert len(updated_files) == 1
    assert updated_files[0].name.endswith("_add_user.py")
    assert not updated_files[0].name.startswith("20260817000000_")


def test_cli_bump_command_lenient_matching(runner: CliRunner, tmp_path: Path) -> None:
    """Verifies bumping a migration script using lenient name matching with spaces."""
    file_path = tmp_path / "20260817000000_add_user.py"
    file_path.write_text(
        manage_migrations_utils.generate_migration_content(
            "Add User", "2026-08-17T00:00:00Z"
        )
    )

    result = runner.invoke(
        cli,
        ["bump", "add user"],
        input="y\n",
    )

    assert result.exit_code == 0
    assert "Planned changes:" in result.output
    assert "Successfully bumped migration script" in result.output
    assert not file_path.exists()
    assert len(list(tmp_path.glob("*_add_user.py"))) == 1


def test_cli_bump_command_aborted(runner: CliRunner, tmp_path: Path) -> None:
    """Verifies aborting a bump when user responds 'n' to confirmation prompt."""
    file_path = tmp_path / "20260817000000_add_user.py"
    file_path.write_text(
        manage_migrations_utils.generate_migration_content(
            "Add User", "2026-08-17T00:00:00Z"
        )
    )

    result = runner.invoke(
        cli,
        ["bump", "add_user"],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Planned changes:" in result.output
    assert "Aborted without making changes." in result.output
    assert file_path.exists()
    assert len(list(tmp_path.glob("*.py"))) == 1


def test_cli_bump_command_with_yes_flag(runner: CliRunner, tmp_path: Path) -> None:
    """Verifies bumping a migration script with -y flag bypasses confirmation prompt."""
    file_path = tmp_path / "20260817000000_add_user.py"
    file_path.write_text(
        manage_migrations_utils.generate_migration_content(
            "Add User", "2026-08-17T00:00:00Z"
        )
    )

    result = runner.invoke(
        cli,
        ["bump", "add_user", "-y"],
    )

    assert result.exit_code == 0
    assert "Planned changes:" in result.output
    assert "Proceed with bump?" not in result.output
    assert "Successfully bumped migration script" in result.output
    assert not file_path.exists()
    assert len(list(tmp_path.glob("*_add_user.py"))) == 1


def test_cli_bump_command_not_found_raises(runner: CliRunner, tmp_path: Path) -> None:
    """Verifies bump command exits with an error if target migration is not found."""
    result = runner.invoke(
        cli,
        ["bump", "missing_table"],
    )
    assert result.exit_code != 0
    assert "No migration script found matching" in result.output


def test_cli_bump_command_invalid_filename_format_raises(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Verifies bump command exits with an error when target script filename is invalid."""
    bad_file = tmp_path / "invalid_script.py"
    bad_file.write_text("class Migration: pass\n")

    result = runner.invoke(cli, ["bump", str(bad_file), "-y"])
    assert result.exit_code != 0
    assert "Invalid migration filename format" in result.output


# ==============================================================================
# 3. 'list' Command Tests
# ==============================================================================


def test_cli_list_command(runner: CliRunner, tmp_path: Path) -> None:
    """Verifies listing discovered migration scripts with table formatting and metadata."""
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

    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert "Found 2 migration script(s)" in result.output
    assert "Timestamp (UTC)" in result.output
    assert "2026-08-17T00:00:00Z" in result.output
    assert "2026-08-18T12:00:00Z" in result.output
    assert "20260817000000_bootstrap.py" in result.output
    assert "20260818120000_add_node.py" in result.output
    assert "Bootstrap schema" in result.output
    assert "Add Node table" in result.output


def test_cli_list_command_empty_dir(runner: CliRunner, tmp_path: Path) -> None:
    """Verifies list command message when no migration scripts are found."""
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "No migration scripts found" in result.output


def test_cli_list_command_dynamic_width_long_filenames(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Verifies list command dynamically adjusts column width for long migration filenames."""
    long_filename = "20260819173510_add_external_observation_identifier_indexes.py"
    (tmp_path / long_filename).write_text(
        manage_migrations_utils.generate_migration_content(
            "Add External Observation Identifier Indexes", "2026-08-19T17:35:10Z"
        )
    )

    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "Found 1 migration script(s)" in result.output
    assert long_filename in result.output
    # Header divider should dynamically scale with filename length
    assert "-" * len(long_filename) in result.output
    assert "Add External Observation Identifier Indexes" in result.output
