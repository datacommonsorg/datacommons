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

"""CI validation tests for all migration scripts in the codebase.

These tests validate that all migration files in `datacommons_db.migrations.migration_scripts`
are discoverable, follow the timestamp naming convention, have unique and valid UTC ISO-8601
creation timestamps matching their filename prefixes, and define valid migration methods.
Any malformed migration script submitted in a PR will fail these tests and block merge in CI.
"""

import ast
import datetime
import inspect
import re
from pathlib import Path

import datacommons_db.migrations.migration_scripts
from datacommons_db.migrations import MigrationRunner

FILENAME_PATTERN = re.compile(r"^(\d{14})_[a-z0-9_]+\.py$")
ISO_8601_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_all_migration_script_files_are_discoverable():
    """Verify that every migration script file on disk in migration_scripts/ is discoverable.

    Ensures that no migration files are accidentally skipped by MigrationRunner.discover_migrations()
    due to missing SchemaMigration inheritance, abstract class definitions, or import issues.
    """
    scripts_dir = Path(datacommons_db.migrations.migration_scripts.__file__).parent
    script_files = [
        f
        for f in scripts_dir.glob("*.py")
        if not f.name.startswith("_") and f.name != "__init__.py"
    ]

    discovered = MigrationRunner.discover_migrations()
    assert len(discovered) == len(script_files), (
        f"Found {len(script_files)} migration files on disk but discover_migrations() found {len(discovered)}. "
        "Ensure all migration files contain a concrete SchemaMigration subclass."
    )


def test_migration_scripts_filename_convention():
    """Verify that migration script filenames match YYYYMMDDHHMMSS_<description>.py format."""
    scripts_dir = Path(datacommons_db.migrations.migration_scripts.__file__).parent

    for file_path in scripts_dir.glob("*.py"):
        if file_path.name.startswith("_") or file_path.name == "__init__.py":
            continue

        match = FILENAME_PATTERN.match(file_path.name)
        assert match is not None, (
            f"Migration script '{file_path.name}' does not follow naming convention "
            f"'YYYYMMDDHHMMSS_<description>.py' (e.g. 20260817000000_bootstrap.py)"
        )


def test_migration_creation_timestamps_are_valid_and_match_filename():
    """Verify that creation_timestamp is valid ISO-8601 UTC and matches the filename prefix."""
    discovered = MigrationRunner.discover_migrations()
    assert discovered, (
        "No migration scripts found. Expected at least 1 migration script."
    )

    for migration in discovered:
        # 1. Format check
        ts_str = migration.creation_timestamp
        assert isinstance(ts_str, str), (
            f"Migration {migration.__class__.__name__} creation_timestamp must be a string, "
            f"found {type(ts_str).__name__}"
        )
        assert ISO_8601_UTC_PATTERN.match(ts_str), (
            f"Migration {migration.__class__.__name__} creation_timestamp '{ts_str}' "
            "must be UTC ISO-8601 formatted as 'YYYY-MM-DDTHH:MM:SSZ'"
        )

        # 2. Parse calendar date/time
        dt = datetime.datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.UTC
        )

        # 3. Filename prefix sync
        module_file = Path(inspect.getfile(migration.__class__)).name
        expected_prefix = dt.strftime("%Y%m%d%H%M%S")
        assert module_file.startswith(expected_prefix), (
            f"Migration {migration.__class__.__name__} timestamp '{ts_str}' does not match "
            f"file prefix '{module_file}'. Expected file to start with '{expected_prefix}_'."
        )


def test_migration_timestamps_are_unique():
    """Verify that all migration creation_timestamps in the repository are strictly unique."""
    discovered = MigrationRunner.discover_migrations()
    assert discovered, (
        "No migration scripts found. Expected at least 1 migration script."
    )

    timestamps = [m.creation_timestamp for m in discovered]
    unique_timestamps = set(timestamps)

    assert len(timestamps) == len(unique_timestamps), (
        f"Duplicate migration timestamps detected in repository: {timestamps}"
    )


def test_migration_scripts_have_non_empty_descriptions():
    """Verify that all migration scripts define a non-empty description."""
    discovered = MigrationRunner.discover_migrations()
    for migration in discovered:
        assert isinstance(migration.description, str), (
            f"Migration {migration.__class__.__name__} description must be a string"
        )
        assert len(migration.description.strip()) > 0, (
            f"Migration {migration.__class__.__name__} must have a non-empty description"
        )


def test_migration_upgrade_signature():
    """Verify that each migration implements callable 'upgrade'."""
    discovered = MigrationRunner.discover_migrations()
    for migration in discovered:
        assert hasattr(migration, "upgrade"), (
            f"Migration {migration.__class__.__name__} must have 'upgrade' attribute"
        )
        assert callable(migration.upgrade), (
            f"Migration {migration.__class__.__name__} 'upgrade' attribute must be callable"
        )


def test_all_migration_scripts_valid_ast_structure():
    """Statically verifies that all migration script files parse as valid AST and define required elements."""
    scripts_dir = Path(datacommons_db.migrations.migration_scripts.__file__).parent
    script_files = [
        f
        for f in scripts_dir.glob("*.py")
        if not f.name.startswith("_") and f.name != "__init__.py"
    ]

    for script_file in script_files:
        content = script_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(script_file))
        assert tree is not None, f"Failed to parse AST for {script_file.name}"

        # Find the SchemaMigration subclass definition
        migration_classes = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and any(
                (isinstance(base, ast.Name) and base.id == "SchemaMigration")
                or (isinstance(base, ast.Attribute) and base.attr == "SchemaMigration")
                for base in node.bases
            )
        ]
        assert len(migration_classes) == 1, (
            f"{script_file.name} must define exactly one 'SchemaMigration' subclass"
        )

        mig_class = migration_classes[0]
        method_names = {
            node.name for node in mig_class.body if isinstance(node, ast.FunctionDef)
        }
        assert "upgrade" in method_names, (
            f"{script_file.name} class {mig_class.name} must define an 'upgrade' method"
        )
