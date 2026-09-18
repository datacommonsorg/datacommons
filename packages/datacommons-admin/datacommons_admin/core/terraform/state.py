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
from pathlib import Path
from typing import Any

import click
from google.cloud import storage
from google.cloud.exceptions import Forbidden, GoogleCloudError, NotFound

from datacommons_admin.core.terraform.models import (
    TerraformOutputs,
    TerraformStateConfig,
)

_OUTPUTS_CACHE_KEY = "terraform_outputs"


def get_default_bucket_name(instance_name: str, project_id: str) -> str:
    """Returns the default Google Cloud Storage bucket name for Terraform state."""
    return f"tf-state-{instance_name}-{project_id}"


def get_default_state_prefix(instance_name: str) -> str:
    """Returns the default Google Cloud Storage object prefix for Terraform state."""
    return f"terraform/state/{instance_name}"


def get_default_state_uri(project_id: str, instance_name: str) -> str:
    """Returns the GCS URI used by the default remote-state configuration."""
    bucket_name = get_default_bucket_name(instance_name, project_id)
    prefix = get_default_state_prefix(instance_name)
    return f"gs://{bucket_name}/{prefix}/default.tfstate"


def _clean_str(value: object | None) -> str | None:
    """Strips whitespace from string values and normalizes empty strings to None."""
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return None


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


def _resolve_gcs_uri(config: TerraformStateConfig) -> str:
    """Computes the fully qualified GCS URI for remote state."""
    if config.tf_state_location:
        return config.tf_state_location

    if config.project_id and config.instance_name:
        return get_default_state_uri(config.project_id, config.instance_name)

    raise click.ClickException(
        "Cannot compute GCS URI for local Terraform state configuration."
    )


def _parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
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


def _download_gcs_blob_text(
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


def _parse_terraform_state_outputs(
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
    gcs_uri = _resolve_gcs_uri(config)
    bucket_name, blob_name = _parse_gcs_uri(gcs_uri)
    content = _download_gcs_blob_text(bucket_name, blob_name, config.project_id)
    return _parse_terraform_state_outputs(content, gcs_uri)


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


def get_terraform_outputs(
    config: TerraformStateConfig | None = None,
) -> TerraformOutputs:
    """Sole public entrypoint to fetch, parse, and validate deployment outputs into a cached, immutable TerraformOutputs dataclass."""
    resolved_config = config or _resolve_remote_state_params()
    ctx = click.get_current_context(silent=True) if config is None else None
    params = ctx.find_object(dict) if ctx else None
    cached: TerraformOutputs | None = params.get(_OUTPUTS_CACHE_KEY) if params else None

    if cached is None:
        raw_outputs = (
            _get_outputs_from_gcs(resolved_config)
            if resolved_config.is_remote
            else _get_outputs_from_local()
        )
        cached = TerraformOutputs.from_state_outputs(raw_outputs)
        if params is not None:
            params[_OUTPUTS_CACHE_KEY] = cached

    return cached
