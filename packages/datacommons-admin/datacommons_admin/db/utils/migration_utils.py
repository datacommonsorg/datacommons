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

import click
from datacommons_db.clients import ExecutionStatus, SpannerClient
from datacommons_db.migrations import MigrationRunner

from datacommons_admin.core.utils.ui_utils import _confirm


def is_database_initialized(spanner_client: SpannerClient) -> bool:
    """Checks whether the Cloud Spanner database exists and contains the Node table.

    Args:
        spanner_client: SpannerClient instance.

    Returns:
        True if the database exists and contains the Node table, False otherwise.
    """
    try:
        return spanner_client.table_exists("Node")
    except Exception:  # noqa: BLE001 - safely detect uninitialized database
        return False


def _apply_migrations(spanner_client: SpannerClient, runner: MigrationRunner) -> bool:
    """Acquires a distributed database lock and applies all pending migrations.

    Args:
        spanner_client: SpannerClient instance used for database lock management.
        runner: MigrationRunner instance used to execute schema migrations.

    Returns:
        True if all migrations were successfully applied.

    Raises:
        click.ClickException: If acquiring the database lock or applying migrations fails.
    """
    lock_acquired = False
    try:
        click.secho(
            "Acquiring database lock directly via Cloud Spanner...",
            fg="bright_black",
        )
        if not spanner_client.acquire_lock(workflow_id="schema-migration"):
            raise click.ClickException(
                "Could not acquire database lock: Lock is currently held by another process or workflow.\n"
                "An ingestion workflow may currently be running. "
                "Please wait for active ingestions to finish before running migrations."
            )
        lock_acquired = True

        click.secho("Applying pending schema migrations...", fg="bright_black")
        pending = runner.get_pending_migrations()

        for migration in pending:
            res = runner.apply_migration(migration)
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
        if lock_acquired:
            click.secho(
                "Releasing database lock directly via Cloud Spanner...",
                fg="bright_black",
            )
            try:
                spanner_client.release_lock(workflow_id="schema-migration")
            except Exception as e:  # noqa: BLE001
                click.secho(
                    f"Warning: {e}",
                    fg="yellow",
                )


def _initialize_database(spanner_client: SpannerClient) -> bool:
    """Initializes a fresh Spanner database with baseline schema and applies all migrations.

    Args:
        spanner_client: SpannerClient instance.

    Returns:
        True if initialization and migrations succeeded.

    Raises:
        click.ClickException: If database is already initialized or initialization/migrations fail.
    """
    db_name = f"{spanner_client.instance_id}/{spanner_client.database_id}"
    if is_database_initialized(spanner_client):
        click.secho(
            f"Spanner database '{db_name}' is already initialized. Skipping initialization and migrations.\n"
            "To apply schema migrations, please run:\n  datacommons admin migrate-db",
            fg="yellow",
        )
        return True

    click.secho(
        f"Initializing baseline schema for Spanner database '{spanner_client.project_id}/{db_name}'...",
        fg="bright_black",
    )
    init_result = spanner_client.initialize_database()
    if init_result.status != ExecutionStatus.SUCCESS:
        raise click.ClickException(
            f"Failed to initialize baseline schema: {init_result.error_message}"
        )
    click.secho("  ✔ Applied baseline schema (schema.sql)", fg="green")

    runner = MigrationRunner(spanner_client=spanner_client)
    pending = runner.get_pending_migrations()
    if not pending:
        click.secho(
            "Database initialized successfully with baseline schema!",
            fg="green",
            bold=True,
        )
        return True

    click.secho(
        f"Applying {len(pending)} schema migration(s)...",
        fg="cyan",
    )
    res = _apply_migrations(spanner_client, runner)
    click.secho("Successfully initialized Spanner database!", fg="green", bold=True)
    return res


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
    spanner_client: SpannerClient,
    *,
    auto_approve: bool = False,
) -> bool:
    """Checks, optionally confirms, and applies pending schema migrations to Spanner.

    Args:
        spanner_client: SpannerClient instance.
        auto_approve: If False, prompts user for interactive confirmation before applying.

    Returns:
        True if migrations were applied or database is already up-to-date, False if cancelled by the user.

    Raises:
        click.ClickException: If checking pending migrations, acquiring the database lock, or applying migrations fails.
    """
    db_name = f"{spanner_client.instance_id}/{spanner_client.database_id}"
    if not is_database_initialized(spanner_client):
        raise click.ClickException(
            f"Database '{db_name}' has not been initialized.\n"
            "Please run 'datacommons admin init-db' to initialize the database."
        )

    click.secho(
        f"Checking schema migrations for Spanner database '{spanner_client.project_id}/{db_name}'...",
        fg="bright_black",
    )
    runner = MigrationRunner(spanner_client=spanner_client)

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
        len(pending), spanner_client.instance_id, spanner_client.database_id
    ):
        click.secho("Migration cancelled.", fg="yellow")
        return False

    # Apply migrations
    return _apply_migrations(spanner_client, runner)
