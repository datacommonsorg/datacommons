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
        """Validate and sort migrations chronologically by creation_timestamp.

        Args:
            migrations: List of SchemaMigration instances.

        Returns:
            Sorted list of SchemaMigration instances.

        Raises:
            ValueError: If migrations have duplicate creation_timestamps.
        """
        if not migrations:
            return []

        sorted_migrations = sorted(migrations, key=lambda m: m.creation_timestamp)

        # Check that there are no duplicates
        seen_timestamps: set[str] = set()
        for migration in sorted_migrations:
            ts = migration.creation_timestamp
            if ts in seen_timestamps:
                raise ValueError(
                    f"Duplicate migration creation_timestamp detected: {ts}"
                )
            seen_timestamps.add(ts)

        return sorted_migrations

    @classmethod
    def discover_migrations(cls) -> list[SchemaMigration]:
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
                    and not inspect.isabstract(obj)
                    and obj.__module__ == module.__name__  # Filter out imported objects
                ):
                    discovered.append(obj())

        return cls.validate_migrations(discovered)

    def get_applied_migrations(self) -> set[str]:
        """Query the target database to determine the set of applied migration creation timestamps.

        Returns:
            Set of applied creation_timestamp strings, or empty set if SchemaVersion table does not exist.

        Raises:
            RuntimeError: If querying SchemaVersion fails unexpectedly.
        """
        if not self.spanner_client.table_exists("SchemaVersion"):
            return set()

        get_applied_migrations_query = "SELECT CreationTimestamp FROM SchemaVersion"
        result = self.spanner_client.execute_query(get_applied_migrations_query)
        if result.status != ExecutionStatus.SUCCESS:
            raise RuntimeError(
                f"Failed to query SchemaVersion table: {result.error_message}"
            )

        applied_migrations: set[str] = set()
        for row in result.rows:
            if not isinstance(row, (list, tuple)) or len(row) == 0:
                raise RuntimeError(
                    f"Invalid or non-indexable row format in SchemaVersion query results: {row!r}"
                )
            applied_migrations.add(str(row[0]))
        return applied_migrations

    def get_pending_migrations(
        self, applied_migrations: set[str] | None = None
    ) -> list[SchemaMigration]:
        """Get the list of pending migrations to be applied in chronological order.

        Args:
            applied_migrations: Optional set of applied migration creation_timestamps.
                If None, queries the database.

        Returns:
            List of SchemaMigration instances that have not yet been applied.
        """
        if applied_migrations is None:
            applied_migrations = self.get_applied_migrations()

        return [
            m for m in self.migrations if m.creation_timestamp not in applied_migrations
        ]

    def apply_migration(self, migration: SchemaMigration) -> None:
        """Apply a single migration and record its completion in SchemaVersion.

        Args:
            migration: The SchemaMigration instance to apply.

        Raises:
            RuntimeError: If migration execution or recording in SchemaVersion fails.
        """
        logger.info(
            "Applying migration %s: %s",
            migration.creation_timestamp,
            migration.description,
        )

        # 1. Execute the migration's upgrade changes
        migration.upgrade(self.spanner_client)

        # 2. Record the applied migration in SchemaVersion
        self.set_schema_version(
            creation_timestamp=migration.creation_timestamp,
            description=migration.description,
        )

        logger.info(
            "Successfully applied migration %s",
            migration.creation_timestamp,
        )

    def set_schema_version(self, creation_timestamp: str, description: str) -> None:
        """Record an applied schema version in the SchemaVersion table.

        Args:
            creation_timestamp: The migration creation_timestamp to record.
            description: Description of the schema migration.

        Raises:
            RuntimeError: If inserting into SchemaVersion fails.
        """
        insert_schema_version_dml = (
            "INSERT INTO SchemaVersion (CreationTimestamp, AppliedTimestamp, Description) "
            "VALUES (@creation_timestamp, PENDING_COMMIT_TIMESTAMP(), @description)"
        )
        params = {
            "creation_timestamp": creation_timestamp,
            "description": description,
        }
        param_types = {
            "creation_timestamp": spanner.param_types.STRING,
            "description": spanner.param_types.STRING,
        }

        dml_result = self.spanner_client.execute_dml(
            insert_schema_version_dml,
            params=params,
            param_types=param_types,
        )
        if dml_result.status != ExecutionStatus.SUCCESS:
            raise RuntimeError(
                f"Failed to record migration {creation_timestamp} in SchemaVersion: "
                f"{dml_result.error_message}"
            )

    def run_migrations(self) -> list[SchemaMigration]:
        """Execute all pending migrations in sequential chronological order.

        Returns:
            List of applied SchemaMigration instances.

        Raises:
            RuntimeError: If any migration fails during execution.
        """
        applied_set = self.get_applied_migrations()
        pending = self.get_pending_migrations(applied_migrations=applied_set)

        if not pending:
            logger.info("Database is already up-to-date. No migrations to apply.")
            return []

        applied: list[SchemaMigration] = []
        for migration in pending:
            try:
                self.apply_migration(migration)
                applied.append(migration)
            except Exception as e:
                logger.error(
                    "Migration %s failed: %s. Halting migration sequence.",
                    migration.creation_timestamp,
                    e,
                )
                raise

        return applied
