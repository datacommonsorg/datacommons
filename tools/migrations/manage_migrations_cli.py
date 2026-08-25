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
  Provides internal developer CLI tooling for creating and managing
  Spanner schema migrations in packages/datacommons-db.

COMMANDS:
  1. create <name> [-d/--description <desc>]
     Auto-generates a timestamped migration script (e.g. 20260819135412_my_change.py)
     pre-populated with license header, SchemaMigration subclass, and UTC ISO-8601 creation_timestamp.

USAGE EXAMPLES:
  # Create a new migration script
  uv run manage-migrations create add_node_tables -d "Add Node and Edge tables"
"""

import click

from tools.migrations import manage_migrations_utils


@click.group(
    help="DevOps tooling for creating and managing Data Commons migration scripts."
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
        )
    except (ValueError, FileExistsError) as e:
        raise click.ClickException(str(e)) from e

    click.secho("✔ Successfully created migration script:", fg="green", bold=True)
    click.echo(f"  - File:        {target_file.name}")
    click.echo(f"  - Timestamp:   {iso_ts}")
    click.echo(f"  - Description: {desc}")


if __name__ == "__main__":
    cli()
