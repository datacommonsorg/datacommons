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

import re

import click

from datacommons_admin.ingestion_helper_client import IngestionHelperClient
from datacommons_admin.ingestion_job_client import IngestionJobClient
from datacommons_admin.tf_utils import (
    get_ingestion_prep_job_name,
    get_ingestion_service_url,
    get_ingestion_workflow_name,
    get_ingestion_workflow_service_account_email,
    get_project_id,
    get_region,
)


@click.group(name="ingest")
def ingest() -> None:
    """Manage data ingestion jobs."""


@ingest.command(name="start")
@click.option(
    "--imports",
    "imports",
    default=None,
    help="The names of the imports to run (comma-separated).",
)
def start(imports: str | None = None) -> None:
    """Start a data ingestion job execution."""
    click.secho("Datacommons Admin Ingest Start", fg="cyan", bold=True)

    click.secho(
        "Fetching Ingestion parameters from Terraform outputs...",
        fg="bright_black",
    )

    helper_url = get_ingestion_service_url()
    job_name = get_ingestion_prep_job_name()
    sa_email = get_ingestion_workflow_service_account_email()
    project_id = get_project_id()
    region = get_region()
    workflow_name = get_ingestion_workflow_name()

    click.secho(f"Found Ingestion Helper URL: {helper_url}", fg="green")
    click.secho(f"Found Data Job Name: {job_name}", fg="green")
    click.secho(f"Found Workflow Service Account: {sa_email}", fg="green")
    click.secho(f"Found GCP Project ID: {project_id}", fg="green")
    click.secho(f"Found GCP Region: {region}", fg="green")
    click.secho(
        "Triggering data ingestion via Ingestion Helper API...",
        fg="bright_black",
    )

    client = IngestionHelperClient(
        helper_url,
        service_account_email=sa_email,
    )
    result = client.start_ingestion(job_name, imports=imports)

    click.secho("Successfully started ingestion job!", fg="green", bold=True)
    res_name = (
        result.get("operationName")
        or result.get("name")
        or result.get("metadata", {}).get("name")
    )

    if res_name:
        op_pattern = r"projects/([^/]+)/locations/([^/]+)/operations/([^/]+)"
        op_match = re.match(op_pattern, res_name)

        if op_match:
            click.secho(f"Operation details: {res_name}", fg="bright_black")
            resp_project_id, location, operation_id = op_match.groups()

            short_job_name = job_name.split("/")[-1] if "/" in job_name else job_name
            job_url = f"https://console.cloud.google.com/run/jobs/details/{location}/{short_job_name}/executions?project={resp_project_id}"

            click.secho("Operation ID: ", fg="cyan", bold=True, nl=False)
            click.secho(operation_id, fg="green")
            click.secho("Job Console Link: ", fg="cyan", bold=True, nl=False)
            click.secho(job_url, fg="blue", underline=True)
        else:
            click.secho(f"Resource details: {res_name}", fg="bright_black")

        click.secho("\n[!] Note on Ingestion Completion", fg="yellow", bold=True)
        click.secho(
            "This job triggers a Cloud Workflow that runs in the background.\n"
            "Check the Workflows console below to verify full completion.",
            fg="yellow",
        )

        workflow_url = f"https://console.cloud.google.com/workflows/workflow/{region}/{workflow_name}/executions?project={project_id}"
        click.secho("Workflow Console Link: ", fg="cyan", bold=True, nl=False)
        click.secho(workflow_url, fg="blue", underline=True)


@ingest.command(name="show-config")
def show_config() -> None:
    """Print the current ingestion job configuration (environment variables)."""
    click.secho("Datacommons Admin Ingest Show-Config", fg="cyan", bold=True)
    click.secho(
        "Fetching Data Job Name and Workflow Service Account from Terraform outputs...",
        fg="bright_black",
    )

    job_name = get_ingestion_prep_job_name()
    sa_email = get_ingestion_workflow_service_account_email()
    project_id = get_project_id()
    region = get_region()

    click.secho(f"Found Data Job Name: {job_name}", fg="green")
    click.secho(f"Found Workflow Service Account: {sa_email}", fg="green")
    click.secho(f"Found GCP Project ID: {project_id}", fg="green")
    click.secho(f"Found GCP Region: {region}", fg="green")
    click.secho(
        f"Fetching configuration for Cloud Run job '{job_name}'...",
        fg="bright_black",
    )

    client = IngestionJobClient(
        job_name,
        service_account_email=sa_email,
        project_id=project_id,
        location=region,
    )
    env_vars = client.get_config()

    click.secho("\nCurrent Ingestion Job Configuration:", fg="cyan", bold=True)
    if not env_vars:
        click.secho("No environment variables configured.", fg="yellow")
    else:
        for env in env_vars:
            name = env.get("name", "UNKNOWN")
            if "value" in env:
                val = env["value"]
            elif "valueSource" in env:
                val = f"[SECRET: {env['valueSource']}]"
            else:
                val = "[UNSET]"
            click.secho(f"  {name}: ", fg="bright_black", nl=False)
            click.secho(str(val), fg="green")
