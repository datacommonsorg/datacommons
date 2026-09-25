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

from typing import NamedTuple

import click
from datacommons_db.clients import SpannerClient

from datacommons_admin.core.terraform.state import get_terraform_outputs
from datacommons_admin.db.utils.migration_utils import (
    _initialize_database,
    _run_migrations,
)


class SpannerCLIContext(NamedTuple):
    """Context object holding initialized Spanner client and deployment target metadata."""

    client: SpannerClient
    project_id: str
    instance_id: str
    database_id: str
    region: str


def _setup_spanner_client(ctx: click.Context) -> SpannerCLIContext:
    click.secho(
        "Fetching Spanner details and region from Terraform outputs...",
        fg="bright_black",
    )

    state_params = ctx.obj or {}
    tf = get_terraform_outputs(
        project_id=state_params.get("project_id"),
        instance_name=state_params.get("instance_name"),
        tf_state_location=state_params.get("tf_state_location"),
    )

    if not tf.spanner_instance_id or not tf.spanner_database_id:
        raise click.ClickException(
            "Cloud Spanner is not enabled or configured in this deployment state. "
            "Ensure 'enable_spanner = true' in your deployment configuration."
        )

    click.secho(
        f"Found Spanner details: project={tf.project_id}, instance={tf.spanner_instance_id}, database={tf.spanner_database_id}, region={tf.region}",
        fg="green",
    )

    client = SpannerClient(
        project_id=tf.project_id,
        instance_id=tf.spanner_instance_id,
        database_id=tf.spanner_database_id,
    )
    return SpannerCLIContext(
        client=client,
        project_id=tf.project_id,
        instance_id=tf.spanner_instance_id,
        database_id=tf.spanner_database_id,
        region=tf.region,
    )


@click.command(name="migrate-db")
@click.option(
    "-y",
    "--yes",
    "auto_approve",
    is_flag=True,
    help="Automatically confirm and apply pending migrations without prompting.",
)
@click.pass_context
def migrate_db(ctx: click.Context, *, auto_approve: bool) -> bool:
    """Apply pending schema migrations to the Spanner database.

    Args:
        ctx: Click execution context containing root admin flags.
        auto_approve: If True, automatically confirms and applies pending migrations without prompting.

    Returns:
        True if migrations were applied or database is already up-to-date, False if cancelled by the user.

    Raises:
        click.ClickException: If reading Terraform outputs, checking pending migrations, acquiring lock, or applying migrations fails.
    """
    click.secho("Datacommons Admin Migrate-DB", fg="cyan", bold=True)
    spanner_ctx = _setup_spanner_client(ctx)
    return _run_migrations(
        spanner_ctx.client,
        auto_approve=auto_approve,
    )


@click.command(name="init-db")
@click.pass_context
def init_db(ctx: click.Context) -> None:
    """Initialize the Spanner database schema and apply all migrations."""
    click.secho("Datacommons Admin Init-DB", fg="cyan", bold=True)
    spanner_ctx = _setup_spanner_client(ctx)

    _initialize_database(spanner_ctx.client)

