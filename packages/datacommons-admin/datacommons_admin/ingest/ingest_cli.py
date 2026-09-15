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
import re

from datacommons_admin.core.clients import IngestionJobClient
from datacommons_admin.core.utils.tf_utils import (
    get_ingestion_workflow_service_account_email,
    get_project_id,
    get_region,
    get_ingestion_workflow_name,
    get_storage_artifacts_bucket_name,
    get_spanner_instance_id,
    get_spanner_database_id,
)


@click.group(name="ingest")
def ingest() -> None:
    """Manage data ingestion jobs."""


@ingest.command(name="start")
@click.option(
    "--imports",
    "imports",
    required=True,
    help="The names of the imports to run (comma-separated).",
)
def start(imports: str) -> None:
    """Start a data ingestion job execution."""
    click.secho("Datacommons Admin Ingest Start", fg="cyan", bold=True)
    click.secho(
        "Fetching workflow details and service accounts from Terraform outputs...",
        fg="bright_black",
    )

    sa_email = get_ingestion_workflow_service_account_email()
    project_id = get_project_id()
    region = get_region()
    workflow_name = get_ingestion_workflow_name()
    bucket_name = get_storage_artifacts_bucket_name()

    spanner_instance = ""
    spanner_database = ""
    try:
        spanner_instance = get_spanner_instance_id()
    except Exception:
        pass
    try:
        spanner_database = get_spanner_database_id()
    except Exception:
        pass

    click.secho(f"Found workflow: {workflow_name}", fg="green")
    click.secho(f"Found workflow service account: {sa_email}", fg="green")
    click.secho(f"Found GCP project ID: {project_id}", fg="green")
    click.secho(f"Found GCP region: {region}", fg="green")
    click.secho(
        f"Starting Cloud Workflow '{workflow_name}' via Executions API (this may take a few moments)...",
        fg="bright_black",
    )

    client = IngestionJobClient(
        workflow_name=workflow_name,
        service_account_email=sa_email,
        project_id=project_id,
        location=region,
    )
    result = client.start_workflow(
        bucket_name=bucket_name,
        spanner_instance=spanner_instance,
        spanner_database=spanner_database,
        imports=imports,
    )

    click.secho("Successfully started ingestion workflow!", fg="green", bold=True)
    res_name = result.get("name")

    if res_name:
        exec_pattern = (
            r"projects/([^/]+)/locations/([^/]+)/workflows/([^/]+)/executions/([^/]+)"
        )
        exec_match = re.match(exec_pattern, res_name)

        if exec_match:
            _, location, wf_name, exec_id = exec_match.groups()
            execution_url = f"https://console.cloud.google.com/workflows/workflow/{location}/{wf_name}/execution/{exec_id}/summary?project={project_id}"

            click.secho("Execution ID: ", fg="cyan", bold=True, nl=False)
            click.secho(exec_id, fg="green")
            click.secho("Execution console link: ", fg="cyan", bold=True, nl=False)
            click.secho(execution_url, fg="blue", underline=True)
        else:
            click.secho(f"Execution resource path: {res_name}", fg="bright_black")


@ingest.command(name="show-config")
def show_config() -> None:
    """Print the current ingestion job configuration (environment variables)."""
    click.secho("Datacommons Admin Ingest Show-Config", fg="cyan", bold=True)
    click.secho(
        "Preprocessing job is managed dynamically by Cloud Workflows / Cloud Batch.\n"
        "No static Cloud Run preprocessor job exists.",
        fg="yellow",
    )
