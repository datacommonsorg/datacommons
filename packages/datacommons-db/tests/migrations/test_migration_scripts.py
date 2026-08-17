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
form a contiguous, valid, properly named version sequence starting from version 0.
Any malformed migration script submitted in a PR will fail these tests and block merge in CI.
"""

import re
from pathlib import Path

import datacommons_db.migrations.migration_scripts
from datacommons_db.migrations import MigrationRunner


def test_all_migration_script_files_are_discoverable():
    """Verify that every migration script file on disk in migration_scripts/ is discoverable.

    Ensures that no migration files are accidentally skipped by MigrationRunner.discover_migrations()
    due to missing SchemaMigration inheritance, abstract class definitions, or import issues.
    """
    scripts_dir = Path(datacommons_db.migrations.migration_scripts.__file__).parent
    script_files = [f for f in scripts_dir.glob("*.py") if not f.name.startswith("_")]

    discovered = MigrationRunner.discover_migrations()
    assert len(discovered) == len(script_files), (
        f"Found {len(script_files)} migration files on disk but discover_migrations() found {len(discovered)}. "
        "Ensure all migration files contain a concrete SchemaMigration subclass."
    )


def test_migration_scripts_version_sequence():
    """Verify that all migration scripts form a contiguous, non-negative sequence starting from 0."""
    migrations = MigrationRunner.discover_migrations()
    assert migrations, "No migration scripts found. Expected at least 1 migration script."

    # 1. Must start at version 0 -> 1
    assert migrations[0].source_version == 0, (
        f"First migration must have source_version=0, found {migrations[0].source_version}"
    )
    assert migrations[0].target_version == 1, (
        f"First migration must have target_version=1, found {migrations[0].target_version}"
    )

    for i, migration in enumerate(migrations):
        # 2. Version bounds
        assert migration.source_version >= 0, (
            f"Migration {migration.__class__.__name__} has negative source_version: {migration.source_version}"
        )
        assert migration.target_version > 0, (
            f"Migration {migration.__class__.__name__} has non-positive target_version: {migration.target_version}"
        )

        # 3. Single-step increment
        assert migration.target_version == migration.source_version + 1, (
            f"Migration {migration.__class__.__name__} must increment version by 1 "
            f"({migration.source_version} -> {migration.target_version})"
        )

        # 4. Contiguity with previous migration
        if i > 0:
            prev = migrations[i - 1]
            assert migration.source_version == prev.target_version, (
                f"Discontinuous migration sequence: gap between {prev.__class__.__name__} "
                f"(target={prev.target_version}) and {migration.__class__.__name__} "
                f"(source={migration.source_version})"
            )


def test_migration_scripts_have_non_empty_descriptions():
    """Verify that all migration scripts define a non-empty description."""
    migrations = MigrationRunner.discover_migrations()
    for migration in migrations:
        assert isinstance(migration.description, str), (
            f"Migration {migration.__class__.__name__} description must be a string"
        )
        assert len(migration.description.strip()) > 0, (
            f"Migration {migration.__class__.__name__} must have a non-empty description"
        )


def test_migration_scripts_filename_convention():
    """Verify that migration script filenames match migration_XXXX_*.py format."""
    scripts_dir = Path(datacommons_db.migrations.migration_scripts.__file__).parent
    pattern = re.compile(r"^migration_(\d{4})_[a-z0-9_]+\.py$")

    for file_path in scripts_dir.glob("*.py"):
        if file_path.name.startswith("_"):
            continue

        match = pattern.match(file_path.name)
        assert match is not None, (
            f"Migration script '{file_path.name}' does not follow naming convention "
            f"'migration_XXXX_<description>.py' (e.g. migration_0001_bootstrap.py)"
        )
