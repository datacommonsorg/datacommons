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

import json
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
        "tools.migrations.manage_migrations_utils.get_default_migrations_dir",
        lambda: tmp_path,
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
    assert f"description: str = {json.dumps('Add Observation table')}" in content
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
    assert f"description: str = {json.dumps('Add indexes')}" in content


def test_cli_create_command_invalid_name_raises(runner: CliRunner) -> None:
    """Verifies create command exits with an error for invalid migration names."""
    result = runner.invoke(cli, ["create", "invalid@name!"])
    assert result.exit_code != 0
    assert "Invalid migration name" in result.output


def test_cli_create_command_duplicate_raises(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies attempting to create a duplicate migration file with the same timestamp errors out."""
    fixed_now = "20260819120000", "2026-08-19T12:00:00Z"
    monkeypatch.setattr(
        "tools.migrations.manage_migrations_utils.generate_utc_timestamps",
        lambda *args, **kwargs: fixed_now,
    )

    res1 = runner.invoke(cli, ["create", "duplicate_name"])
    assert res1.exit_code == 0

    res2 = runner.invoke(cli, ["create", "duplicate_name"])
    assert res2.exit_code != 0
    assert "already exists" in res2.output


def test_cli_create_command_os_error_raises(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies filesystem OSError is caught and surfaced as a clean ClickException."""

    def mock_create_error(*args, **kwargs):
        raise PermissionError("Permission denied: cannot write to migrations dir")

    monkeypatch.setattr(
        "tools.migrations.manage_migrations_utils.create_migration_file",
        mock_create_error,
    )

    result = runner.invoke(cli, ["create", "test_permission_error"])
    assert result.exit_code != 0
    assert "Permission denied: cannot write to migrations dir" in result.output
