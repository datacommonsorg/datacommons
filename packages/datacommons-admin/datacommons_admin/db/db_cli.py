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

from typing import Any, Tuple

import click

from datacommons_admin.db.ingestion_helper_client import IngestionHelperClient
from datacommons_admin.db.migration_utils import _run_migrations
from datacommons_admin.utils.tf_utils import (
    get_ingestion_service_url,
    get_ingestion_workflow_service_account_email,
    get_project_id,
    get_spanner_database_id,
    get_spanner_instance_id,
)


def _setup_ingestion_client() -> Tuple[IngestionHelperClient, str, str, str]:
    click.secho(
        "Fetching ingestion service URL, workflow service account, and Spanner details from Terraform outputs...",
        fg="bright_black",
    )

    url = get_ingestion_service_url()
    sa_email = get_ingestion_workflow_service_account_email()
    project_id = get_project_id()
    instance_id = get_spanner_instance_id()
    database_id = get_spanner_database_id()

    click.secho(f"Found ingestion service URL: {url}", fg="green")
    click.secho(f"Found ingestion workflow service account: {sa_email}", fg="green")
    click.secho(
        f"Found Spanner details: project={project_id}, instance={instance_id}, database={database_id}",
        fg="green",
    )

    client = IngestionHelperClient(url, service_account_email=sa_email)
    return client, project_id, instance_id, database_id


def _run_seed_db(client: Any, instance_id: str, database_id: str) -> None:
    click.secho(
        f"Seeding Spanner database '{instance_id}/{database_id}' via the Ingestion Helper service (this may take a few moments)...",
        fg="bright_black",
    )
    result = client.seed_database()
    click.secho("Successfully seeded Spanner database!", fg="green", bold=True)
    message = result.get("message")
    if message:
        click.secho(f"Details: {message}", fg="bright_black")


@click.command(name="migrate-db")
@click.option(
    "-y",
    "--yes",
    "auto_approve",
    is_flag=True,
    help="Automatically confirm and apply pending migrations without prompting.",
)
def migrate_db(auto_approve: bool) -> bool:
    """Apply pending schema migrations to the Spanner database.

    Args:
        auto_approve: If True, automatically confirms and applies pending migrations without prompting.

    Returns:
        True if migrations were applied or database is already up-to-date, False if cancelled by the user.

    Raises:
        click.ClickException: If reading Terraform outputs, checking pending migrations, acquiring lock, or applying migrations fails.
    """
    click.secho("Datacommons Admin Migrate-DB", fg="cyan", bold=True)
    client, project_id, instance_id, database_id = _setup_ingestion_client()
    return _run_migrations(
        client,
        project_id,
        instance_id,
        database_id,
        auto_approve=auto_approve,
    )


@click.command(name="init-db")
@click.option(
    "--init-only", is_flag=True, help="Only initialize the database without seeding."
)
def init_db(init_only: bool) -> None:
    """Initialize (and by default seed) the Spanner database via the DCP Ingestion Helper service."""
    click.secho("Datacommons Admin Init-DB", fg="cyan", bold=True)
    client, project_id, instance_id, database_id = _setup_ingestion_client()

    click.secho(
        f"Initializing Spanner database '{instance_id}/{database_id}' via the Ingestion Helper service (this may take a few moments)...",
        fg="bright_black",
    )
    result = client.initialize_database()

    click.secho("Successfully initialized Spanner database!", fg="green", bold=True)
    message = result.get("message")
    if message:
        click.secho(f"Details: {message}", fg="bright_black")

    _run_migrations(
        client,
        project_id,
        instance_id,
        database_id,
        auto_approve=True,
    )

    if not init_only:
        _run_seed_db(client, instance_id, database_id)


@click.command(name="seed-db")
def seed_db() -> None:
    """Seed the Spanner database via the DCP Ingestion Helper service."""
    click.secho("Datacommons Admin Seed-DB", fg="cyan", bold=True)
    client, _project_id, instance_id, database_id = _setup_ingestion_client()
    _run_seed_db(client, instance_id, database_id)
