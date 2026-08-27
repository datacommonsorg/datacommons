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

from typing import Any

import click

from datacommons_admin.core.clients import IngestionHelperClient
from datacommons_admin.core.utils.ui_utils import _confirm
from datacommons_db.clients import SpannerClient
from datacommons_db.migrations import MigrationRunner


def _is_database_initialized(
    project_id: str, instance_id: str, database_id: str
) -> bool:
    """Checks whether the Cloud Spanner database exists and has been initialized.

    Args:
        project_id: GCP project ID hosting the Spanner database.
        instance_id: Cloud Spanner instance ID.
        database_id: Cloud Spanner database ID.

    Returns:
        True if the database exists and contains the Node table, False otherwise.
    """
    try:
        spanner_client = SpannerClient(
            project_id=project_id,
            instance_id=instance_id,
            database_id=database_id,
        )
        return spanner_client.table_exists("Node")
    except Exception:  # noqa: BLE001 - must catch all exceptions to safely detect initialization status
        return False


def _create_migration_runner(
    project_id: str, instance_id: str, database_id: str
) -> MigrationRunner:
    """Initializes a SpannerClient and returns a MigrationRunner instance.

    Args:
        project_id: GCP project ID hosting the Spanner database.
        instance_id: Cloud Spanner instance ID.
        database_id: Cloud Spanner database ID.

    Returns:
        A MigrationRunner instance initialized with a SpannerClient.

    Raises:
        click.ClickException: If initialization of the SpannerClient or MigrationRunner fails.
    """
    try:
        spanner_client = SpannerClient(
            project_id=project_id,
            instance_id=instance_id,
            database_id=database_id,
        )
        return MigrationRunner(spanner_client=spanner_client)
    except Exception as e:
        raise click.ClickException(f"Failed to initialize migration runner: {e}") from e


def _apply_migrations(client: Any, runner: MigrationRunner) -> bool:
    """Acquires a distributed database lock and applies all pending migrations.

    Args:
        client: IngestionHelperClient instance used for database lock management.
        runner: MigrationRunner instance used to execute schema migrations.

    Returns:
        True if all migrations were successfully applied.

    Raises:
        click.ClickException: If acquiring the database lock or applying migrations fails.
    """
    # Attempt to acquire Spanner database lock via the Ingestion Helper service.
    click.secho(
        "Acquiring database lock via the Ingestion Helper service...",
        fg="bright_black",
    )
    client.acquire_lock(workflow_id="schema-migration")

    try:
        # Apply all pending migrations
        click.secho("Applying pending schema migrations...", fg="bright_black")
        results = runner.run_migrations()

        for res in results:
            click.secho(
                f"  ✔ Applied migration {res.creation_timestamp}: {res.description}",
                fg="green",
            )
        click.secho(
            "Successfully applied all schema migrations!", fg="green", bold=True
        )
        return True
    except Exception as e:
        raise click.ClickException(f"Failed to apply schema migrations: {e}") from e
    finally:
        # Always attempt to release the database lock after migration attempt
        click.secho(
            "Releasing database lock via the Ingestion Helper service...",
            fg="bright_black",
        )
        try:
            client.release_lock(workflow_id="schema-migration")
        except Exception as e:
            click.secho(
                f"Warning: {e}",
                fg="yellow",
            )


def _confirm_migration(num_pending: int, instance_id: str, database_id: str) -> bool:
    """Displays a safety warning and prompts the user to confirm applying migrations.

    Args:
        num_pending: Number of pending schema migrations.
        instance_id: Cloud Spanner instance ID.
        database_id: Cloud Spanner database ID.

    Returns:
        True if the user confirms the migration prompt, False otherwise.
    """
    click.secho(
        "\nWarning: Schema migrations will modify your Spanner database schema. "
        "It is strongly recommended to create a database backup before proceeding in production environments.",
        fg="yellow",
    )
    return _confirm(
        f"Apply {num_pending} pending schema migration(s) to Spanner database '{instance_id}/{database_id}'?",
        default=False,
    )


def _run_migrations(
    client: IngestionHelperClient,
    project_id: str,
    instance_id: str,
    database_id: str,
    auto_approve: bool = False,
) -> bool:
    """Checks, optionally confirms, and applies pending schema migrations to Spanner.

    Args:
        client: IngestionHelperClient instance.
        project_id: GCP project ID hosting the Spanner database.
        instance_id: Cloud Spanner instance ID.
        database_id: Cloud Spanner database ID.
        auto_approve: If False, prompts user for interactive confirmation before applying.

    Returns:
        True if migrations were applied or database is already up-to-date, False if cancelled by the user.

    Raises:
        click.ClickException: If checking pending migrations, acquiring the database lock, or applying migrations fails.
    """
    click.secho(
        f"Checking schema migrations for Spanner database '{project_id}/{instance_id}/{database_id}'...",
        fg="bright_black",
    )
    runner = _create_migration_runner(project_id, instance_id, database_id)

    # Fetch pending migrations.
    try:
        pending = runner.get_pending_migrations()
    except Exception as e:
        raise click.ClickException(f"Failed to check pending migrations: {e}") from e

    # Return early if there are no pending migrations.
    if not pending:
        click.secho(
            "Database schema is already up-to-date. No migrations to apply.",
            fg="green",
        )
        return True

    click.secho(f"Found {len(pending)} pending schema migration(s):", fg="cyan")
    for m in pending:
        click.echo(f"  - {m.creation_timestamp}: {m.description}")

    # Ask user for confirmation if not auto-approved
    if not auto_approve and not _confirm_migration(
        len(pending), instance_id, database_id
    ):
        click.secho("Migration cancelled.", fg="yellow")
        return False

    # Apply migrations
    return _apply_migrations(client, runner)
