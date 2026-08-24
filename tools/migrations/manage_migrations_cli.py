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

"""tools.migrations.manage_migrations_cli - Developer DevOps CLI for Schema Migrations.

PURPOSE:
  Provides internal developer CLI tooling for creating, updating, and listing
  Spanner schema migrations in packages/datacommons-db.

COMMANDS:
  1. create <name> [-d/--description <desc>]
     Auto-generates a timestamped migration script (e.g. 20260819135412_my_change.py)
     pre-populated with license header, SchemaMigration subclass, and UTC ISO-8601 creation_timestamp.

  2. bump <target> [-y/--yes]
     Re-timestamps an existing migration script with the current UTC time (both in filename
     and creation_timestamp attribute). Used when resolving merge conflicts as multiple developers
     add migrations concurrently.

  3. list
     Lists all migration scripts discovered in chronological order with metadata and validation status.

USAGE EXAMPLES:
  # Create a new migration script
  uv run manage-migrations create add_node_tables -d "Add Node and Edge tables"

  # Bump an existing migration script during merge conflict / rebase
  uv run manage-migrations bump add_node_tables
  # or by filename
  uv run manage-migrations bump 20260819135412_add_node_tables.py

  # List all migrations
  uv run manage-migrations list
"""

import datetime

import click

from tools.migrations import manage_migrations_utils


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
    description: str | None = None,
) -> None:
    """Create a new timestamped schema migration script."""
    try:
        # Generate new migration script boilerplate on disk
        target_file, iso_ts, desc = manage_migrations_utils.create_migration_file(
            name=name,
            description=description,
            migrations_dir=manage_migrations_utils.DEFAULT_MIGRATIONS_DIR,
        )
    except (ValueError, FileExistsError) as e:
        raise click.ClickException(str(e)) from e

    click.secho("✔ Successfully created migration script:", fg="green", bold=True)
    click.echo(f"  - File:        {target_file.name}")
    click.echo(f"  - Timestamp:   {iso_ts}")
    click.echo(f"  - Description: {desc}")


@cli.command(name="bump")
@click.argument("target")
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    help="Automatically confirm bump without interactive prompt.",
)
def bump_command(target: str, *, yes: bool = False) -> None:
    """Re-timestamp an existing migration script with the current UTC time."""
    try:
        # Locate target migration file and validate filename format
        file_path = manage_migrations_utils.find_migration_file(
            target, manage_migrations_utils.DEFAULT_MIGRATIONS_DIR
        )
        match = manage_migrations_utils.FILENAME_PATTERN.match(file_path.name)
        if not match:
            raise click.ClickException(
                f"Invalid migration filename format: {file_path.name}"
            )

        # Generate new timestamp and projected filename
        now = datetime.datetime.now(datetime.UTC)
        new_prefix, new_iso = manage_migrations_utils.generate_utc_timestamps(now)
        new_filename = f"{new_prefix}_{match.group(2)}.py"

        # Preview planned changes and prompt user for confirmation
        click.echo(f"Found migration script: {file_path.name}")
        click.echo("Planned changes:")
        click.echo(f"  - Rename to:      {new_filename}")
        click.echo(f"  - New timestamp:  {new_iso}")
        if not yes and not click.confirm("Proceed with bump?", default=False):
            click.echo("Aborted without making changes.")
            return

        # Apply timestamp update and rename file
        old_file, new_file, new_iso = manage_migrations_utils.update_migration_file(
            target=file_path,
            migrations_dir=manage_migrations_utils.DEFAULT_MIGRATIONS_DIR,
            target_dt=now,
        )
    except (FileNotFoundError, ValueError, FileExistsError) as e:
        raise click.ClickException(str(e)) from e

    click.secho("✔ Successfully bumped migration script:", fg="green", bold=True)
    click.echo(f"  - Old File:      {old_file.name}")
    click.echo(f"  - New File:      {new_file.name}")
    click.echo(f"  - New Timestamp: {new_iso}")


@cli.command(name="list")
def list_command() -> None:
    """List all migration scripts in chronological order."""
    # Discover all migration scripts with metadata
    migrations = manage_migrations_utils.discover_migrations(
        manage_migrations_utils.DEFAULT_MIGRATIONS_DIR
    )

    # Handle case where no migrations are found
    if not migrations:
        click.echo("No migration scripts found.")
        return

    # Print summary header
    click.secho(f"Found {len(migrations)} migration script(s):", fg="cyan", bold=True)
    click.echo()

    # Dynamically compute column width for Filename to prevent column misalignment
    idx_col_width = 4
    ts_col_width = 22
    fn_col_width = max(len("Filename"), max(len(m.filename) for m in migrations))
    desc_divider_width = 30

    # Format and print table headers
    header_idx = "#".ljust(idx_col_width)
    header_ts = "Timestamp (UTC)".ljust(ts_col_width)
    header_filename = "Filename".ljust(fn_col_width)
    header_desc = "Description"
    click.secho(
        f"  {header_idx} {header_ts} {header_filename} {header_desc}",
        bold=True,
    )
    click.echo(
        f"  {'-' * idx_col_width} {'-' * ts_col_width} {'-' * fn_col_width} {'-' * desc_divider_width}"
    )

    # Print each migration record in chronological order
    for info in migrations:
        row_idx = str(info.index).ljust(idx_col_width)
        row_ts = info.creation_timestamp.ljust(ts_col_width)
        row_filename = info.filename.ljust(fn_col_width)
        click.echo(f"  {row_idx} {row_ts} {row_filename} {info.description}")


if __name__ == "__main__":
    cli()
