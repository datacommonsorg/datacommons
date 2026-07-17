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
import shutil
import subprocess
from pathlib import Path
from typing import Any

import click

TF_OUTPUT_INGESTION_SERVICE_URL = "ingestion_service_url"
TF_OUTPUT_INGESTION_WORKFLOW_SERVICE_ACCOUNT_EMAIL = (
    "ingestion_workflow_service_account_email"
)
TF_OUTPUT_SPANNER_INSTANCE_ID = "spanner_instance_id"
TF_OUTPUT_SPANNER_DATABASE_ID = "spanner_database_id"
TF_OUTPUT_INGESTION_PREP_JOB_NAME = "ingestion_prep_job_name"
TF_OUTPUT_PROJECT_ID = "project_id"
TF_OUTPUT_REGION = "region"
TF_OUTPUT_INGESTION_WORKFLOW_NAME = "ingestion_workflow_name"

DEFAULT_STATE_FILE_NAME = "default.tfstate"
_SUBPROCESS_TIMEOUT_SECONDS = 20


def _resolve_state_location() -> tuple[str | None, str | None]:
    """Extracts state location and project ID from Click context hierarchy.

    Returns:
        tuple[gcs_uri | None, project_id | None]: GCS URI and GCP project ID if remote,
        or (None, None) if local.
    """
    ctx = click.get_current_context(silent=True)
    project_id: str | None = None
    instance_name: str | None = None
    tf_state_loc: str | None = None

    cur = ctx
    while cur:
        if isinstance(cur.obj, dict):
            project_id = project_id or cur.obj.get("project_id")
            instance_name = instance_name or cur.obj.get("instance_name")
            tf_state_loc = tf_state_loc or cur.obj.get("tf_state_location")
        cur = cur.parent

    project_id = (project_id or "").strip() or None
    instance_name = (instance_name or "").strip() or None
    tf_state_loc = (tf_state_loc or "").strip() or None

    if tf_state_loc:
        if not tf_state_loc.endswith(".tfstate"):
            tf_state_loc = f"{tf_state_loc.rstrip('/')}/{DEFAULT_STATE_FILE_NAME}"
        return tf_state_loc, project_id

    if project_id and instance_name:
        uri = (
            f"gs://tf-state-{instance_name}-{project_id}"
            f"/terraform/state/{instance_name}/{DEFAULT_STATE_FILE_NAME}"
        )
        return uri, project_id

    if bool(project_id) != bool(instance_name):
        raise click.ClickException(
            "Both --project-id and --instance-name must be specified together to locate remote state."
        )

    return None, None


def _get_outputs_from_gcs(gcs_uri: str, project_id: str | None) -> dict[str, Any]:
    """Downloads and parses Terraform state outputs from Google Cloud Storage."""
    from google.cloud import storage
    from google.cloud.exceptions import Forbidden, NotFound

    match = re.match(r"^gs://([^/]+)/(.+)$", gcs_uri)
    if not match:
        raise click.ClickException(
            f"Invalid GCS URI '{gcs_uri}'. Must match 'gs://<bucket>/<object>'."
        )
    bucket_name, blob_name = match.group(1), match.group(2)

    try:
        client = storage.Client(project=project_id) if project_id else storage.Client()
        blob = client.bucket(bucket_name).blob(blob_name)
        content = blob.download_as_text()
    except NotFound as e:
        raise click.ClickException(
            f"Terraform state file not found at '{gcs_uri}'.\n"
            "Please verify that the --project-id, --instance-name, or --tf-state-location flags are correct and that resources were deployed."
        ) from e
    except Forbidden as e:
        raise click.ClickException(
            f"Permission denied accessing Terraform state at '{gcs_uri}': {e}.\n"
            f"Please ensure your GCP account has 'roles/storage.objectViewer' on bucket '{bucket_name}'."
        ) from e
    except Exception as e:
        raise click.ClickException(
            f"Failed to download Terraform state from GCS at '{gcs_uri}': {e}"
        ) from e

    try:
        state_data = json.loads(content)
    except json.JSONDecodeError as e:
        raise click.ClickException(
            f"Failed to parse Terraform state at '{gcs_uri}' as valid JSON."
        ) from e

    if not isinstance(state_data, dict):
        raise click.ClickException(
            f"Invalid Terraform state format at '{gcs_uri}'. Expected a JSON object."
        )

    outputs = state_data.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        raise click.ClickException(
            f"No outputs found in the Terraform state file at '{gcs_uri}'.\n"
            "Please verify that your deployment is active and that variables are exported."
        )

    return outputs


def _get_outputs_from_local() -> dict[str, Any]:
    """Runs `terraform output -json` locally."""
    terraform_path = shutil.which("terraform")
    if not terraform_path:
        raise click.ClickException(
            "Terraform CLI not found. Please ensure Terraform is installed and available in your PATH."
        )

    try:
        result = subprocess.run(  # noqa: S603
            [terraform_path, "output", "-json"],
            capture_output=True,
            text=True,
            check=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as e:
        raise click.ClickException(
            f"'terraform output -json' timed out after {_SUBPROCESS_TIMEOUT_SECONDS}s."
        ) from e
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() or e.stdout.strip() or "Unknown error"
        raise click.ClickException(
            "Failed to run 'terraform output'.\n"
            "To resolve your deployment configuration, either:\n"
            "a. Run this command inside your initialized DCP Terraform deployment directory (where 'terraform apply' has been run).\n"
            "b. Specify the GCS remote state flags on the 'admin' group: --project-id <id> and --instance-name <name> (or --tf-state-location <gcs_uri>).\n\n"
            f"Error details: {error_msg}"
        ) from e
    except OSError as e:
        raise click.ClickException(f"Failed to execute Terraform process: {e}") from e

    try:
        outputs = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise click.ClickException(
            "Failed to parse 'terraform output -json'. The output was not valid JSON."
        ) from e

    if not isinstance(outputs, dict) or not outputs:
        cwd = Path.cwd()
        has_tf_files = (
            (cwd / ".terraform").exists()
            or (cwd / "terraform.tfstate").exists()
            or (cwd / "main.tf").exists()
        )
        if not has_tf_files:
            raise click.ClickException(
                f"No Terraform deployment state found in '{cwd}'.\n"
                "To resolve your deployment configuration, either:\n"
                "a. Navigate to your initialized DCP Terraform directory (where 'terraform apply' has been run).\n"
                "b. Run the command with GCS remote state flags on the 'admin' group: --project-id <id> and --instance-name <name> (or --tf-state-location <gcs_uri>)."
            )
        raise click.ClickException(
            f"No Terraform outputs found in '{cwd}'.\n"
            "Please ensure you have successfully run 'terraform apply' to generate the deployment state."
        )

    return outputs


def _get_terraform_outputs() -> dict[str, Any]:
    """Retrieves all Terraform outputs, caching them in Click context for the current command."""
    ctx = click.get_current_context(silent=True)
    cur = ctx
    while cur:
        if isinstance(cur.obj, dict) and "_tf_outputs_cache" in cur.obj:
            return cur.obj["_tf_outputs_cache"]
        cur = cur.parent

    gcs_uri, project_id = _resolve_state_location()
    if gcs_uri:
        outputs = _get_outputs_from_gcs(gcs_uri, project_id)
    else:
        outputs = _get_outputs_from_local()

    if ctx and isinstance(ctx.obj, dict):
        ctx.obj["_tf_outputs_cache"] = outputs

    return outputs


def get_terraform_output(key: str) -> str:
    """Fetches a specific key from Terraform output (local or remote GCS state)."""
    outputs = _get_terraform_outputs()

    if key not in outputs:
        gcs_uri, _ = _resolve_state_location()
        location_desc = f"GCS URI '{gcs_uri}'" if gcs_uri else f"'{Path.cwd()}'"
        raise click.ClickException(
            f"Terraform output key '{key}' not found in {location_desc}.\n"
            "Please verify that your Terraform configuration exports this output."
        )

    output_entry = outputs[key]
    if isinstance(output_entry, dict) and "value" in output_entry:
        raw_val = output_entry["value"]
    else:
        raw_val = output_entry

    if raw_val is None or (isinstance(raw_val, str) and not raw_val.strip()):
        raise click.ClickException(
            f"Terraform output '{key}' is empty or null. Please verify your deployment state."
        )

    return str(raw_val)


def get_ingestion_service_url() -> str:
    """Convenience wrapper to fetch the ingestion_service_url Terraform output."""
    return get_terraform_output(TF_OUTPUT_INGESTION_SERVICE_URL)


def get_ingestion_workflow_service_account_email() -> str:
    """Convenience wrapper to fetch the ingestion_workflow_service_account_email Terraform output."""
    return get_terraform_output(TF_OUTPUT_INGESTION_WORKFLOW_SERVICE_ACCOUNT_EMAIL)


def get_spanner_instance_id() -> str:
    """Convenience wrapper to fetch the spanner_instance_id Terraform output."""
    return get_terraform_output(TF_OUTPUT_SPANNER_INSTANCE_ID)


def get_spanner_database_id() -> str:
    """Convenience wrapper to fetch the spanner_database_id Terraform output."""
    return get_terraform_output(TF_OUTPUT_SPANNER_DATABASE_ID)


def get_ingestion_prep_job_name() -> str:
    """Convenience wrapper to fetch the ingestion_prep_job_name Terraform output."""
    return get_terraform_output(TF_OUTPUT_INGESTION_PREP_JOB_NAME)


def get_project_id() -> str:
    """Convenience wrapper to fetch the project_id Terraform output."""
    return get_terraform_output(TF_OUTPUT_PROJECT_ID)


def get_region() -> str:
    """Convenience wrapper to fetch the region Terraform output."""
    return get_terraform_output(TF_OUTPUT_REGION)


def get_ingestion_workflow_name() -> str:
    """Convenience wrapper to fetch the ingestion_workflow_name Terraform output."""
    return get_terraform_output(TF_OUTPUT_INGESTION_WORKFLOW_NAME)
