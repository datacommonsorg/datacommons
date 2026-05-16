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

from datacommons_admin.ingestion_job_client import IngestionJobClient
from datacommons_admin.tf_utils import (
    get_cdc_data_job_name,
    get_dcp_orchestrator_service_account_email,
    get_dcp_project_id,
)


@click.group(name="ingest")
def ingest() -> None:
    """Manage data ingestion jobs."""


@ingest.command(name="start")
def start() -> None:
    """Start a data ingestion job execution."""
    click.secho("Datacommons Admin Ingest Start", fg="cyan", bold=True)
    click.secho(
        "Fetching Data Job Name and Orchestrator Service Account from Terraform outputs...",
        fg="bright_black",
    )

    job_name = get_cdc_data_job_name()
    sa_email = get_dcp_orchestrator_service_account_email()
    project_id = get_dcp_project_id()

    click.secho(f"Found Data Job Name: {job_name}", fg="green")
    click.secho(f"Found Orchestrator Service Account: {sa_email}", fg="green")
    click.secho(f"Found GCP Project ID: {project_id}", fg="green")
    click.secho(
        f"Starting Cloud Run job '{job_name}' via Admin API (this may take a few moments)...",
        fg="bright_black",
    )

    client = IngestionJobClient(job_name, service_account_email=sa_email, project_id=project_id)
    result = client.start_job()

    click.secho("Successfully started ingestion job!", fg="green", bold=True)
    exec_name = result.get("name") or result.get("metadata", {}).get("name")
    if exec_name:
        click.secho(f"Execution details: {exec_name}", fg="bright_black")

        parts = exec_name.split("/")
        if (
            len(parts) >= 8
            and parts[0] == "projects"
            and parts[2] == "locations"
            and parts[4] == "jobs"
            and parts[6] == "executions"
        ):
            project_id = parts[1]
            location = parts[3]
            job_id = parts[5]
            execution_id = parts[7]

            job_url = f"https://console.cloud.google.com/run/jobs/details/{location}/{job_id}/executions?project={project_id}"
            exec_url = f"https://console.cloud.google.com/run/jobs/executions/details/{location}/{execution_id}?project={project_id}"

            click.secho("Job ID: ", fg="cyan", bold=True, nl=False)
            click.secho(job_id, fg="green")
            click.secho("Execution ID: ", fg="cyan", bold=True, nl=False)
            click.secho(execution_id, fg="green")
            click.secho("Job Console Link: ", fg="cyan", bold=True, nl=False)
            click.secho(job_url, fg="blue", underline=True)
            click.secho("Execution Console Link: ", fg="cyan", bold=True, nl=False)
            click.secho(exec_url, fg="blue", underline=True)


@ingest.command(name="show-config")
def show_config() -> None:
    """Print the current ingestion job configuration (environment variables)."""
    click.secho("Datacommons Admin Ingest Show-Config", fg="cyan", bold=True)
    click.secho(
        "Fetching Data Job Name and Orchestrator Service Account from Terraform outputs...",
        fg="bright_black",
    )

    job_name = get_cdc_data_job_name()
    sa_email = get_dcp_orchestrator_service_account_email()

    click.secho(f"Found Data Job Name: {job_name}", fg="green")
    click.secho(f"Found Orchestrator Service Account: {sa_email}", fg="green")
    click.secho(
        f"Fetching configuration for Cloud Run job '{job_name}'...",
        fg="bright_black",
    )

    client = IngestionJobClient(job_name, service_account_email=sa_email)
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
