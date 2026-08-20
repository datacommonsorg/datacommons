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

"""CLI command tests for developer migration DevOps tooling (tools/migrations/migrations.py)."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from tools.migrations import migration_utils
from tools.migrations.migrations import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_migrations_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolates CLI tests to a temporary directory."""
    monkeypatch.setattr("tools.migrations.migrations.DEFAULT_MIGRATIONS_DIR", tmp_path)
    return tmp_path


# ==============================================================================
# Click CLI Command Tests (tools/migrations/migrations.py)
# ==============================================================================


def test_cli_create_command(runner: CliRunner, tmp_path: Path) -> None:
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
    match = migration_utils.FILENAME_PATTERN.match(created_file.name)
    assert match is not None

    content = created_file.read_text()
    assert 'description: str = "Add Observation table"' in content
    assert "SchemaMigration" in content


def test_cli_create_command_duplicate_raises(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "tools.migrations.migration_utils.get_utc_timestamps",
        lambda _target_dt=None: ("20260819120000", "2026-08-19T12:00:00Z"),
    )
    res1 = runner.invoke(cli, ["create", "add_table"])
    assert res1.exit_code == 0

    res2 = runner.invoke(cli, ["create", "add_table"])
    assert res2.exit_code != 0
    assert "already exists" in res2.output


def test_cli_update_command_confirmed(runner: CliRunner, tmp_path: Path) -> None:
    file_path = tmp_path / "20260817000000_add_user.py"
    file_path.write_text(
        migration_utils.generate_migration_content("Add User", "2026-08-17T00:00:00Z")
    )

    result = runner.invoke(
        cli,
        ["update", "add_user"],
        input="y\n",
    )

    assert result.exit_code == 0
    assert "Planned changes:" in result.output
    assert "Proceed with update?" in result.output
    assert "Successfully updated migration script" in result.output
    assert not file_path.exists()

    updated_files = list(tmp_path.glob("*.py"))
    assert len(updated_files) == 1
    assert updated_files[0].name.endswith("_add_user.py")
    assert not updated_files[0].name.startswith("20260817000000_")


def test_cli_update_command_aborted(runner: CliRunner, tmp_path: Path) -> None:
    file_path = tmp_path / "20260817000000_add_user.py"
    file_path.write_text(
        migration_utils.generate_migration_content("Add User", "2026-08-17T00:00:00Z")
    )

    result = runner.invoke(
        cli,
        ["update", "add_user"],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Planned changes:" in result.output
    assert "Aborted without making changes." in result.output
    # Original file should remain untouched
    assert file_path.exists()
    assert len(list(tmp_path.glob("*.py"))) == 1


def test_cli_update_command_not_found_raises(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(
        cli,
        ["update", "missing_table"],
    )
    assert result.exit_code != 0
    assert "No migration script found matching" in result.output


def test_cli_list_command(runner: CliRunner, tmp_path: Path) -> None:
    (tmp_path / "20260817000000_bootstrap.py").write_text(
        migration_utils.generate_migration_content(
            "Bootstrap schema", "2026-08-17T00:00:00Z"
        )
    )
    (tmp_path / "20260818120000_add_node.py").write_text(
        migration_utils.generate_migration_content(
            "Add Node table", "2026-08-18T12:00:00Z"
        )
    )

    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert "Found 2 migration script(s)" in result.output
    assert "20260817000000_bootstrap.py" in result.output
    assert "20260818120000_add_node.py" in result.output
    assert "Bootstrap schema" in result.output
    assert "Add Node table" in result.output


def test_cli_list_command_empty_dir(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "No migration scripts found" in result.output
