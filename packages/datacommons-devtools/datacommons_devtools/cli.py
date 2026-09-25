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

"""datacommons_devtools.cli - Unified DevOps CLI for Data Commons Platform internal developer tools.

Provides a unified entrypoint for developer tooling under `datacommons-devtools`
(short alias: `dc-devtools`).

USAGE EXAMPLES:
  # Create a new migration script
  uv run datacommons-devtools migrations create add_node_tables -d "Add Node and Edge tables"

  # Bump an existing migration script during merge conflict / rebase
  uv run datacommons-devtools migrations bump add_node_tables
"""

import click

from datacommons_devtools.migrations.cli import cli as migrations_cli


@click.group(
    name="datacommons-devtools",
    help="Unified DevOps CLI suite for Data Commons Platform developer tooling.",
)
def cli() -> None:
    """Data Commons Platform developer CLI tools."""


# Register subcommand suites
cli.add_command(migrations_cli, name="migrations")


if __name__ == "__main__":
    cli()
