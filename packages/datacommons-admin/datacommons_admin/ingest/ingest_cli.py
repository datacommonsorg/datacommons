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

from datacommons_admin.core.clients import IngestionJobClient
from datacommons_admin.core.terraform.state import get_terraform_outputs


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
@click.pass_context
def start(ctx: click.Context, imports: str) -> None:
    """Start a data ingestion job execution."""
    click.secho("Datacommons Admin Ingest Start", fg="cyan", bold=True)
    click.secho(
        "Fetching ingestion configuration from Terraform outputs...",
        fg="bright_black",
    )

    state_params = ctx.obj or {}
    tf = get_terraform_outputs(
        project_id=state_params.get("project_id"),
        instance_name=state_params.get("instance_name"),
        tf_state_location=state_params.get("tf_state_location"),
    )

    click.secho(f"Found workflow: {tf.ingestion_workflow_name}", fg="green")
    click.secho(
        f"Found workflow service account: {tf.ingestion_workflow_service_account_email}",
        fg="green",
    )
    click.secho(f"Found GCP project ID: {tf.project_id}", fg="green")
    click.secho(f"Found GCP region: {tf.region}", fg="green")
    click.secho(
        f"Starting Cloud Workflow '{tf.ingestion_workflow_name}' via Executions API (this may take a few moments)...",
        fg="bright_black",
    )

    client = IngestionJobClient(
        workflow_name=tf.ingestion_workflow_name,
        service_account_email=tf.ingestion_workflow_service_account_email,
        project_id=tf.project_id,
        location=tf.region,
    )
    result = client.start_workflow(imports=imports)

    click.secho("Successfully started ingestion workflow!", fg="green", bold=True)
    res_name = result.get("name")

    if res_name:
        exec_pattern = (
            r"projects/([^/]+)/locations/([^/]+)/workflows/([^/]+)/executions/([^/]+)"
        )
        exec_match = re.match(exec_pattern, res_name)

        if exec_match:
            _, location, wf_name, exec_id = exec_match.groups()
            execution_url = f"https://console.cloud.google.com/workflows/workflow/{location}/{wf_name}/execution/{exec_id}/summary?project={tf.project_id}"

            click.secho("Execution ID: ", fg="cyan", bold=True, nl=False)
            click.secho(exec_id, fg="green")
            click.secho("Execution console link: ", fg="cyan", bold=True, nl=False)
            click.secho(execution_url, fg="blue", underline=True)
        else:
            click.secho(f"Execution resource path: {res_name}", fg="bright_black")


@ingest.command(name="show-config")
@click.pass_context
def show_config(ctx: click.Context) -> None:
    """Print the ingestion job configuration from Terraform outputs."""
    click.secho("Datacommons Admin Ingest Show-Config", fg="cyan", bold=True)
    click.secho(
        "Fetching ingestion configuration from Terraform outputs...",
        fg="bright_black",
    )

    state_params = ctx.obj or {}
    tf = get_terraform_outputs(
        project_id=state_params.get("project_id"),
        instance_name=state_params.get("instance_name"),
        tf_state_location=state_params.get("tf_state_location"),
    )

    # Names match the env vars the workflow passes to the preprocessing job.
    config = {
        "PROJECT_ID": tf.project_id,
        "REGION": tf.region,
        "GCP_SPANNER_INSTANCE_ID": tf.spanner_instance_id,
        "GCP_SPANNER_DATABASE_NAME": tf.spanner_database_id,
        "GCS_BUCKET": tf.storage_artifacts_bucket_name,
    }

    click.secho("\nCurrent ingestion job configuration:", fg="cyan", bold=True)
    for name, val in config.items():
        click.secho(f"  {name}: ", fg="bright_black", nl=False)
        click.secho(val or "[UNSET]", fg="green")
