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

"""tools.migrations.cli - Developer DevOps CLI for Schema Migrations.

PURPOSE:
  Provides internal developer CLI tooling for creating and managing
  Spanner schema migrations in packages/datacommons-db.

COMMANDS:
  1. create <NAME> [-d/--description <desc>]
     Auto-generates a timestamped migration script (e.g. 20260819135412_my_change.py)
     pre-populated with license header, SchemaMigration subclass, and UTC ISO-8601 creation_timestamp.

  2. bump <NAME|FILE|PREFIX> [-y/--yes]
     Re-timestamps an existing migration script with the current UTC time (both in filename
     and creation_timestamp attribute). Used when resolving merge conflicts as multiple developers
     add migrations concurrently.

USAGE EXAMPLES:
  # Create a new migration script
  uv run dcp-tools migrations create add_node_tables -d "Add Node and Edge tables"

  # Bump an existing migration script during merge conflict / rebase
  uv run dcp-tools migrations bump add_node_tables
  # or by filename
  uv run dcp-tools migrations bump 20260819135412_add_node_tables.py
"""

import datetime

import click

from tools.migrations import utils


@click.group(
    help="DevOps tooling for creating and managing Data Commons migration scripts."
)
def cli() -> None:
    """Data Commons migration devOps CLI."""


@cli.command(name="create")
@click.argument("name", metavar="<NAME>")
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
        target_file, iso_ts, desc = utils.create_migration_file(
            name=name,
            description=description,
        )
    except (ValueError, OSError) as e:
        raise click.ClickException(str(e)) from e

    click.secho("✔ Successfully created migration script:", fg="green", bold=True)
    click.echo(f"  - File:        {target_file.name}")
    click.echo(f"  - Timestamp:   {iso_ts}")
    click.echo(f"  - Description: {desc}")


@cli.command(
    name="bump",
    short_help="Re-timestamp an existing migration script with the current UTC time.",
)
@click.argument("target", metavar="<NAME|FILE|PREFIX>", required=False)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    default=False,
    help="Automatically confirm bump without interactive prompt.",
)
def bump_command(target: str | None = None, *, yes: bool = False) -> None:
    """Re-timestamp an existing migration script with the current UTC time.

    TARGET (<NAME|FILE|PREFIX>) can be:
      - A migration change name (e.g. 'add_edge_indexes')
      - A 14-digit timestamp prefix (e.g. '20260819135412')
      - A migration filename (e.g. '20260819135412_add_edge_indexes.py')
      - A relative or absolute file path to the migration script
    """
    if not target:
        raise click.UsageError(
            "Missing argument '<NAME|FILE|PREFIX>'.\n\n"
            "Please specify which migration script to bump. Examples:\n"
            "  - By name:     uv run dcp-tools migrations bump add_edge_indexes\n"
            "  - By prefix:   uv run dcp-tools migrations bump 20260819135412\n"
            "  - By filename: uv run dcp-tools migrations bump 20260819135412_add_edge_indexes.py"
        )

    try:
        # Locate target migration file and validate filename format
        file_path = utils.find_migration_file(target)
        match = utils.FILENAME_PATTERN.match(file_path.name)
        if not match:
            raise click.ClickException(
                f"Invalid migration filename format: {file_path.name}"
            )

        # Generate new timestamp and projected filename
        now = datetime.datetime.now(datetime.UTC)
        new_prefix, new_iso = utils.generate_utc_timestamps(now)
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
        old_file, new_file, new_iso = utils.update_migration_file(
            target=file_path,
            target_dt=now,
        )
    except (ValueError, OSError) as e:
        raise click.ClickException(str(e)) from e

    click.secho("✔ Successfully bumped migration script:", fg="green", bold=True)
    click.echo(f"  - Old File:      {old_file.name}")
    click.echo(f"  - New File:      {new_file.name}")
    click.echo(f"  - New Timestamp: {new_iso}")


if __name__ == "__main__":
    cli()
