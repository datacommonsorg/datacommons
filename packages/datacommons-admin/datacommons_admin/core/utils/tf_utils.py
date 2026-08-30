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
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
from google.cloud import storage
from google.cloud.exceptions import Forbidden, GoogleCloudError, NotFound

from datacommons_admin.init.utils.gcs_utils import get_default_state_uri

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

_OUTPUTS_CACHE_KEY = "terraform_outputs"


def _clean_str(value: object | None) -> str | None:
    """Strips whitespace from string values and normalizes empty strings to None."""
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return None


@dataclass(frozen=True)
class TerraformStateConfig:
    """Encapsulates and validates configuration parameters for locating Terraform state.

    Attributes:
        project_id: GCP project ID used for canonical bucket derivation and GCS client auth.
        instance_name: DCP instance name prefix used for canonical bucket and object path derivation.
        tf_state_location: Explicit GCS URI pointing directly to the Terraform state file.
    """

    project_id: str | None = None
    instance_name: str | None = None
    tf_state_location: str | None = None

    def __post_init__(self) -> None:
        """Validates configuration combinations upon initialization."""
        if not self.tf_state_location and (
            bool(self.project_id) != bool(self.instance_name)
        ):
            raise click.ClickException(
                "Both --project-id and --instance-name must be specified together to locate remote state."
            )

    @property
    def is_remote(self) -> bool:
        """Determines whether remote GCS state resolution should be used."""
        return bool(self.tf_state_location or (self.project_id and self.instance_name))

    @property
    def gcs_uri(self) -> str:
        """Computes the fully qualified GCS URI for remote state."""
        if self.tf_state_location:
            return self.tf_state_location

        if self.project_id and self.instance_name:
            return get_default_state_uri(self.project_id, self.instance_name)

        raise click.ClickException(
            "Cannot compute GCS URI for local Terraform state configuration."
        )

    @property
    def location_description(self) -> str:
        """Returns a human-readable description of the state location for error messages."""
        if self.tf_state_location:
            return f"GCS URI '{self.tf_state_location}'"
        if self.project_id and self.instance_name:
            return (
                f"GCP project: '{self.project_id}' / instance: '{self.instance_name}'"
            )
        return f"'{Path.cwd()}'"


def _resolve_remote_state_params() -> TerraformStateConfig:
    """Extracts and validates remote-state parameters from the Click context."""
    ctx = click.get_current_context(silent=True)
    params = ctx.find_object(dict) if ctx else None
    params = params or {}

    return TerraformStateConfig(
        project_id=_clean_str(params.get("project_id")),
        instance_name=_clean_str(params.get("instance_name")),
        tf_state_location=_clean_str(params.get("tf_state_location")),
    )


def parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    """Parses and validates a Google Cloud Storage URI into bucket and blob name components."""
    if not gcs_uri.startswith("gs://"):
        raise click.ClickException(
            f"Invalid GCS URI '{gcs_uri}'. Must start with 'gs://'."
        )

    path_part = gcs_uri[len("gs://") :]
    parts = path_part.split("/", 1)
    if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
        raise click.ClickException(
            f"Invalid GCS URI '{gcs_uri}'. Must specify bucket and object path."
        )

    return parts[0].strip(), parts[1].strip()


def download_gcs_blob_text(
    bucket_name: str, blob_name: str, project_id: str | None = None
) -> str:
    """Downloads the text content of a GCS blob with structured error handling."""
    gcs_uri = f"gs://{bucket_name}/{blob_name}"

    try:
        client = storage.Client(project=project_id) if project_id else storage.Client()
    except Exception as e:
        raise click.ClickException(
            f"Failed to initialize Google Cloud Storage client: {e}.\n"
            "Please ensure you are authenticated via 'gcloud auth application-default login'."
        ) from e

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    try:
        return blob.download_as_text()
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
    except GoogleCloudError as e:
        raise click.ClickException(
            f"Failed to download Terraform state from GCS at '{gcs_uri}': {e}"
        ) from e


def parse_terraform_state_outputs(
    state_json_str: str, source_description: str
) -> dict[str, Any]:
    """Parses raw Terraform state JSON and extracts the outputs dictionary."""
    try:
        state_data = json.loads(state_json_str)
    except json.JSONDecodeError as e:
        raise click.ClickException(
            f"Failed to parse Terraform state at '{source_description}' as valid JSON."
        ) from e

    if not isinstance(state_data, dict):
        raise click.ClickException(
            f"Invalid Terraform state format at '{source_description}'. Expected a JSON object."
        )

    outputs = state_data.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        raise click.ClickException(
            f"No outputs found in the Terraform state file at '{source_description}'.\n"
            "Please verify that your deployment is active and that variables are exported."
        )

    return outputs


def _get_outputs_from_gcs(
    config: TerraformStateConfig,
) -> dict[str, Any]:
    """Downloads and parses Terraform outputs directly from GCS remote state."""
    gcs_uri = config.gcs_uri
    bucket_name, blob_name = parse_gcs_uri(gcs_uri)
    content = download_gcs_blob_text(bucket_name, blob_name, config.project_id)
    return parse_terraform_state_outputs(content, gcs_uri)


def _get_outputs_from_local() -> dict[str, Any]:
    """Runs `terraform output -json` locally with contextual validation."""
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
        )
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


def get_terraform_output(
    key: str,
    config: TerraformStateConfig | None = None,
) -> str:
    """Fetches a specific key from Terraform output (local or remote GCS state)."""
    resolved_config = config or _resolve_remote_state_params()
    ctx = click.get_current_context(silent=True) if config is None else None
    params = ctx.find_object(dict) if ctx else None
    outputs = params.get(_OUTPUTS_CACHE_KEY) if params else None

    if outputs is None:
        if resolved_config.is_remote:
            outputs = _get_outputs_from_gcs(resolved_config)
        else:
            outputs = _get_outputs_from_local()
        if params is not None:
            params[_OUTPUTS_CACHE_KEY] = outputs

    if key not in outputs:
        raise click.ClickException(
            f"Terraform output key '{key}' not found in {resolved_config.location_description}.\n"
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
