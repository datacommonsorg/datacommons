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

import json
import re

import click
from rich.console import Console

from datacommons_admin.core.clients import IngestionJobClient
from datacommons_admin.core.terraform.models import TerraformOutputs
from datacommons_admin.core.terraform.state import get_terraform_outputs
from datacommons_admin.ingest import report as report_lib

_EXECUTION_PATTERN = (
    r"projects/([^/]+)/locations/([^/]+)/workflows/([^/]+)/executions/([^/]+)"
)

_wait_option = click.option(
    "--wait/--no-wait",
    default=None,
    help="Wait for the ingestion report and print it. "
    "Default: wait for dry runs, don't wait for ingestion.",
)
_timeout_option = click.option(
    "--timeout",
    type=int,
    default=1800,
    show_default=True,
    help="Seconds to wait for the report.",
)
_json_option = click.option(
    "--json", "as_json", is_flag=True, help="Print the report as raw JSON."
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
@click.option(
    "--mode",
    type=click.Choice(["ingest", "dry_run"], case_sensitive=False),
    default="ingest",
    show_default=True,
    help="dry_run only preprocesses the data and writes the ingestion report; "
    "nothing is written to Spanner.",
)
@_wait_option
@_timeout_option
@_json_option
@click.pass_context
def start(
    ctx: click.Context,
    *,
    imports: str,
    mode: str,
    wait: bool | None,
    timeout: int,
    as_json: bool,
) -> None:
    """Start a data ingestion job execution."""
    click.secho("Datacommons Admin Ingest Start", fg="cyan", bold=True)
    tf = _terraform_outputs(ctx)

    click.secho(f"Found workflow: {tf.ingestion_workflow_name}", fg="green")
    click.secho(
        f"Found workflow service account: {tf.ingestion_workflow_service_account_email}",
        fg="green",
    )
    click.secho(f"Found GCP project ID: {tf.project_id}", fg="green")
    click.secho(f"Found GCP region: {tf.region}", fg="green")

    client = _job_client(tf)
    dry_run = mode.lower() == "dry_run"
    if dry_run and not client.supports_dry_run():
        raise click.ClickException(
            f"The deployed workflow '{tf.ingestion_workflow_name}' doesn't support "
            "dry runs yet. Apply the latest Terraform before using --mode=dry_run."
        )

    click.secho(
        f"Starting Cloud Workflow '{tf.ingestion_workflow_name}' via Executions API (this may take a few moments)...",
        fg="bright_black",
    )
    result = client.start_workflow(
        imports=imports, mode="DRY_RUN" if dry_run else "INGEST"
    )
    click.secho("Successfully started ingestion workflow!", fg="green", bold=True)

    res_name = result.get("name") or ""
    exec_match = re.match(_EXECUTION_PATTERN, res_name)
    if not exec_match:
        click.secho(f"Execution resource path: {res_name}", fg="bright_black")
        return

    _, location, wf_name, exec_id = exec_match.groups()
    execution_url = f"https://console.cloud.google.com/workflows/workflow/{location}/{wf_name}/execution/{exec_id}/summary?project={tf.project_id}"
    click.secho("Execution ID: ", fg="cyan", bold=True, nl=False)
    click.secho(exec_id, fg="green")
    click.secho("Execution console link: ", fg="cyan", bold=True, nl=False)
    click.secho(execution_url, fg="blue", underline=True)

    if dry_run if wait is None else wait:
        _wait_and_print_report(
            ctx, tf, client, exec_id, timeout=timeout, as_json=as_json
        )


@ingest.command(name="report")
@click.argument("execution_id")
@click.option(
    "--wait/--no-wait",
    default=False,
    help="Wait for the report if it isn't written yet.",
)
@_timeout_option
@_json_option
@click.pass_context
def report(
    ctx: click.Context, execution_id: str, *, wait: bool, timeout: int, as_json: bool
) -> None:
    """Print the ingestion report of a workflow execution."""
    tf = _terraform_outputs(ctx)
    if wait:
        _wait_and_print_report(
            ctx, tf, _job_client(tf), execution_id, timeout=timeout, as_json=as_json
        )
        return
    uri = _report_uri(tf, execution_id)
    found = report_lib.read_report(uri, tf.project_id)
    if found is None:
        raise click.ClickException(
            f"No ingestion report at {uri} yet. Use --wait to wait for it."
        )
    _print_report(ctx, found, uri, as_json=as_json)


def _terraform_outputs(ctx: click.Context) -> TerraformOutputs:
    click.secho(
        "Fetching ingestion configuration from Terraform outputs...",
        fg="bright_black",
    )
    state_params = ctx.obj or {}
    return get_terraform_outputs(
        project_id=state_params.get("project_id"),
        instance_name=state_params.get("instance_name"),
        tf_state_location=state_params.get("tf_state_location"),
    )


def _job_client(tf: TerraformOutputs) -> IngestionJobClient:
    return IngestionJobClient(
        workflow_name=tf.ingestion_workflow_name,
        service_account_email=tf.ingestion_workflow_service_account_email,
        project_id=tf.project_id,
        location=tf.region,
    )


def _report_uri(tf: TerraformOutputs, execution_id: str) -> str:
    if not tf.storage_artifacts_bucket_name or not tf.ingestion_artifacts_path:
        raise click.ClickException(
            "Terraform outputs 'storage_artifacts_bucket_name' and "
            "'ingestion_artifacts_path' are needed to find the ingestion report."
        )
    return report_lib.report_uri(
        tf.storage_artifacts_bucket_name, tf.ingestion_artifacts_path, execution_id
    )


def _wait_and_print_report(
    ctx: click.Context,
    tf: TerraformOutputs,
    client: IngestionJobClient,
    execution_id: str,
    *,
    timeout: int,
    as_json: bool,
) -> None:
    uri = _report_uri(tf, execution_id)
    click.secho(f"Waiting for the ingestion report at {uri}...", fg="bright_black")
    found = report_lib.wait_for_report(
        uri,
        lambda: client.get_execution(execution_id).get("state", ""),
        project_id=tf.project_id,
        timeout=timeout,
    )
    _print_report(ctx, found, uri, as_json=as_json)


def _print_report(ctx: click.Context, found: dict, uri: str, *, as_json: bool) -> None:
    """Prints the report; exits with status 1 if the preprocessor failed."""
    if as_json:
        click.echo(json.dumps(found, indent=2))
    else:
        report_lib.print_report(found, Console())
        click.secho(f"Full report: {uri}", fg="bright_black")
    if found.get("run", {}).get("status") == "FAILURE":
        ctx.exit(1)


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
