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

import importlib
import inspect
import logging
import pkgutil

from google.cloud import spanner

import datacommons_db.migrations.migration_scripts
from datacommons_db.clients.spanner_client import ExecutionStatus, SpannerClient
from datacommons_db.migrations.base import SchemaMigration

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Discovers, validates, plans, and executes Spanner database schema migrations."""

    def __init__(
        self,
        spanner_client: SpannerClient,
        migrations: list[SchemaMigration] | None = None,
    ) -> None:
        """Initialize the MigrationRunner.

        Args:
            spanner_client: SpannerClient instance.
            migrations: Optional explicit list of SchemaMigration instances.
                If omitted, migrations will be automatically discovered.
        """
        self.spanner_client = spanner_client
        if migrations is not None:
            self.migrations = self.validate_migrations(migrations)
        else:
            self.migrations = self.discover_migrations()

    @staticmethod
    def validate_migrations(
        migrations: list[SchemaMigration],
    ) -> list[SchemaMigration]:
        """Validate and sort migrations into a contiguous sequence.

        Args:
            migrations: List of SchemaMigration instances.

        Returns:
            Sorted list of SchemaMigration instances.

        Raises:
            ValueError: If migrations have gaps, duplicates, or invalid version transitions.
        """
        if not migrations:
            return []

        sorted_migrations = sorted(migrations, key=lambda m: m.source_version)
        seen_sources: set[int] = set()
        seen_targets: set[int] = set()

        for i, migration in enumerate(sorted_migrations):
            # Check version bounds
            if migration.source_version < 0:
                raise ValueError(
                    f"Migration source_version must be non-negative (>= 0), but found {migration.source_version}"
                )
            if migration.target_version <= 0:
                raise ValueError(
                    f"Migration target_version must be positive (> 0), but found {migration.target_version}"
                )

            # Check for duplicate source or target versions
            if migration.source_version in seen_sources:
                raise ValueError(
                    f"Duplicate source_version {migration.source_version} found across migrations"
                )
            if migration.target_version in seen_targets:
                raise ValueError(
                    f"Duplicate target_version {migration.target_version} found across migrations"
                )

            seen_sources.add(migration.source_version)
            seen_targets.add(migration.target_version)

            # Check single step increment
            expected_target = migration.source_version + 1
            if migration.target_version != expected_target:
                raise ValueError(
                    f"Migration with source_version {migration.source_version} must have target_version "
                    f"{expected_target}, but found {migration.target_version}"
                )

            # Check continuity with previous migration
            if i > 0:
                prev_migration = sorted_migrations[i - 1]
                if migration.source_version != prev_migration.target_version:
                    raise ValueError(
                        f"Discontinuous migration sequence: gap between target_version "
                        f"{prev_migration.target_version} and source_version {migration.source_version}"
                    )

        return sorted_migrations

    def discover_migrations(self) -> list[SchemaMigration]:
        """Automatically discover and validate all SchemaMigration subclasses in migration_scripts.

        Returns:
            Sorted, validated list of SchemaMigration instances.
        """
        discovered: list[SchemaMigration] = []

        # Only iterate through files from __path__.
        # This prevents external path injection or local file execution when running a packaged release.
        for module_info in pkgutil.iter_modules(
            datacommons_db.migrations.migration_scripts.__path__
        ):
            if module_info.name.startswith("_"):
                # Treat files starting with _ as private, do not import.
                continue
            module = importlib.import_module(
                f"datacommons_db.migrations.migration_scripts.{module_info.name}"
            )
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, SchemaMigration)
                    and obj.__module__ == module.__name__  # Filter out imported objects
                ):
                    discovered.append(obj())

        return self.validate_migrations(discovered)

    def get_current_version(self) -> int:
        """Query the target database to determine the current applied schema version.

        Returns:
            The version number with the most recent AppliedTimestamp, or 0 if SchemaVersion table does not exist or is empty.

        Raises:
            RuntimeError: If querying SchemaVersion fails unexpectedly.
        """
        if not self.spanner_client.table_exists("SchemaVersion"):
            return 0

        query = (
            "SELECT Version FROM SchemaVersion "
            "ORDER BY AppliedTimestamp DESC, Version DESC LIMIT 1"
        )
        result = self.spanner_client.execute_query(query)
        if result.status != ExecutionStatus.SUCCESS:
            raise RuntimeError(
                f"Failed to query SchemaVersion table: {result.error_message}"
            )

        if not result.rows:
            return 0

        return int(result.rows[0][0])

    def get_pending_migrations(
        self, current_version: int | None = None
    ) -> list[SchemaMigration]:
        """Get the list of pending migrations to be applied.

        Args:
            current_version: Optional current version override. If None, queries the database.

        Returns:
            List of SchemaMigration instances that have source_version >= current_version.
        """
        if current_version is None:
            current_version = self.get_current_version()

        if self.migrations:
            latest_available_version = self.migrations[-1].target_version
            if current_version > latest_available_version:
                logger.warning(
                    "Database schema version (%d) is ahead of the latest migration known to this codebase (%d). "
                    "You may be running an outdated version of the datacommons-db package.",
                    current_version,
                    latest_available_version,
                )

        return [m for m in self.migrations if m.source_version >= current_version]

    def apply_migration(self, migration: SchemaMigration) -> None:
        """Apply a single migration and record its completion in SchemaVersion.

        Args:
            migration: The SchemaMigration instance to apply.

        Raises:
            RuntimeError: If migration execution or recording in SchemaVersion fails.
        """
        logger.info(
            "Applying migration %d -> %d: %s",
            migration.source_version,
            migration.target_version,
            migration.description,
        )

        # 1. Execute the migration's forward changes
        migration.roll_forward(self.spanner_client)

        # 2. Record the applied migration version in SchemaVersion
        self.set_schema_version(
            version=migration.target_version,
            description=migration.description,
        )

        logger.info(
            "Successfully applied migration %d -> %d",
            migration.source_version,
            migration.target_version,
        )

    def set_schema_version(self, version: int, description: str) -> None:
        """Record an applied schema version in the SchemaVersion table.

        Args:
            version: The applied version number to record.
            description: Description of the schema migration.

        Raises:
            RuntimeError: If inserting into SchemaVersion fails.
        """
        insert_query = (
            "INSERT INTO SchemaVersion (Version, AppliedTimestamp, Description) "
            "VALUES (@version, PENDING_COMMIT_TIMESTAMP(), @description)"
        )
        params = {
            "version": version,
            "description": description,
        }
        param_types = {
            "version": spanner.param_types.INT64,
            "description": spanner.param_types.STRING,
        }

        dml_res = self.spanner_client.execute_dml(
            insert_query,
            params=params,
            param_types=param_types,
        )
        if dml_res.status != ExecutionStatus.SUCCESS:
            raise RuntimeError(
                f"Failed to record migration version {version} in SchemaVersion: "
                f"{dml_res.error_message}"
            )

    def run_migrations(self) -> list[SchemaMigration]:
        """Execute all pending migrations in sequential order.

        Returns:
            List of applied SchemaMigration instances.

        Raises:
            RuntimeError: If any migration fails during execution.
        """
        current_version = self.get_current_version()
        pending = self.get_pending_migrations(current_version=current_version)

        if not pending:
            logger.info(
                "Database is already up-to-date at version %d. No migrations to apply.",
                current_version,
            )
            return []

        applied: list[SchemaMigration] = []
        for migration in pending:
            try:
                self.apply_migration(migration)
                applied.append(migration)
            except Exception as e:
                logger.error(
                    "Migration %d -> %d failed: %s. Halting migration sequence.",
                    migration.source_version,
                    migration.target_version,
                    e,
                )
                raise

        return applied
