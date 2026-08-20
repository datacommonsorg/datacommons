#!/usr/bin/env python3
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

"""tools.migrations.migrations - Developer DevOps CLI for Schema Migrations.

PURPOSE:
  Provides internal developer CLI tooling for creating, updating, and listing
  Spanner schema migrations in packages/datacommons-db.

COMMANDS:
  1. create <name> [-d/--description <desc>]
     Auto-generates a timestamped migration script (e.g. 20260819135412_my_change.py)
     pre-populated with license header, SchemaMigration subclass, and UTC ISO-8601 creation_timestamp.

  2. update <target>
     Re-timestamps an existing migration script with the current UTC time (both in filename
     and creation_timestamp attribute). Used when resolving merge conflicts as multiple developers
     add migrations concurrently.

  3. list
     Lists all migration scripts discovered in chronological order with metadata and validation status.

USAGE EXAMPLES:
  # Create a new migration script
  uv run manage-migrations create add_node_tables -d "Add Node and Edge tables"

  # Update an existing migration script during merge conflict / rebase
  uv run manage-migrations update add_node_tables
  # or by filename
  uv run manage-migrations update 20260819135412_add_node_tables.py

  # List all migrations
  uv run manage-migrations list
"""

import sys
from pathlib import Path

# Ensure repository root is on sys.path for standalone script execution
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import click

from tools.migrations import migration_utils


@click.group(
    help="DevOps tooling for creating, updating, and listing Data Commons migration scripts."
)
def cli() -> None:
    """Data Commons migration devOps CLI."""


@cli.command(name="create")
@click.argument("name")
@click.option(
    "-d",
    "--description",
    default=None,
    help="Human-readable description of the migration.",
)
def create_command(
    name: str,
    description: str | None,
) -> None:
    """Create a new timestamped schema migration script."""
    try:
        target_file, iso_ts, desc = migration_utils.create_migration_file(
            name=name,
            description=description,
            migrations_dir=migration_utils.DEFAULT_MIGRATIONS_DIR,
        )
    except (ValueError, FileExistsError) as e:
        raise click.ClickException(str(e)) from e

    click.secho("✔ Successfully created migration script:", fg="green", bold=True)
    click.echo(f"  - File:        {target_file}")
    click.echo(f"  - Timestamp:   {iso_ts}")
    click.echo(f"  - Description: {desc}")


@cli.command(name="update")
@click.argument("target")
def update_command(target: str) -> None:
    """Re-timestamp an existing migration script with the current UTC time."""
    try:
        file_path = migration_utils.find_migration_file(
            target, migration_utils.DEFAULT_MIGRATIONS_DIR
        )
        match = migration_utils.FILENAME_PATTERN.match(file_path.name)
        if not match:
            raise click.ClickException(
                f"Invalid migration filename format: {file_path.name}"
            )
        new_prefix, new_iso = migration_utils.get_utc_timestamps()
        new_filename = f"{new_prefix}_{match.group(2)}.py"

        click.echo(f"Found migration script: {file_path.name}")
        click.echo("Planned changes:")
        click.echo(f"  - Rename to:      {new_filename}")
        click.echo(f"  - New timestamp:  {new_iso}")
        if not click.confirm("Proceed with update?", default=False):
            click.echo("Aborted without making changes.")
            return

        old_file, new_file, new_iso = migration_utils.update_migration_file(
            target=file_path,
            migrations_dir=migration_utils.DEFAULT_MIGRATIONS_DIR,
        )
    except (FileNotFoundError, ValueError, FileExistsError) as e:
        raise click.ClickException(str(e)) from e

    click.secho("✔ Successfully updated migration script:", fg="green", bold=True)
    click.echo(f"  - Old File:      {old_file.name}")
    click.echo(f"  - New File:      {new_file.name}")
    click.echo(f"  - New Timestamp: {new_iso}")


@cli.command(name="list")
def list_command() -> None:
    """List all migration scripts in chronological order."""
    migrations = migration_utils.discover_migrations(
        migration_utils.DEFAULT_MIGRATIONS_DIR
    )

    if not migrations:
        click.echo("No migration scripts found.")
        return

    click.secho(f"Found {len(migrations)} migration script(s):", fg="cyan", bold=True)
    click.echo()

    # Table headers
    header_idx = "#".ljust(4)
    header_prefix = "Timestamp (File)".ljust(18)
    header_filename = "Filename".ljust(42)
    header_desc = "Description"
    click.secho(
        f"  {header_idx} {header_prefix} {header_filename} {header_desc}",
        bold=True,
    )
    click.echo(f"  {'-' * 4} {'-' * 18} {'-' * 42} {'-' * 30}")

    for info in migrations:
        row_idx = str(info.index).ljust(4)
        row_prefix = info.prefix_timestamp.ljust(18)
        row_filename = info.filename.ljust(42)
        click.echo(f"  {row_idx} {row_prefix} {row_filename} {info.description}")


if __name__ == "__main__":
    cli()
