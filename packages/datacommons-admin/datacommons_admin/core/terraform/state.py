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

import contextlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import click
from google.cloud import storage
from google.cloud.exceptions import Forbidden, GoogleCloudError, NotFound

from datacommons_admin.core.terraform.models import TerraformOutputs


def get_default_bucket_name(instance_name: str, project_id: str) -> str:
    """Returns the default Google Cloud Storage bucket name for Terraform state."""
    return f"tf-state-{instance_name}-{project_id}"


def get_default_state_prefix(instance_name: str) -> str:
    """Returns the default Google Cloud Storage object prefix for Terraform state."""
    return f"terraform/state/{instance_name}"


def _resolve_remote_state_gcs_uri(
    project_id: str | None = None,
    instance_name: str | None = None,
    tf_state_location: str | None = None,
) -> str | None:
    """Returns the remote GCS state URI if remote flags are provided, or None for local state."""
    if tf_state_location:
        return tf_state_location

    if bool(project_id) != bool(instance_name):
        raise click.ClickException(
            "Both --project-id and --instance-name must be specified together to locate remote state."
        )

    if project_id and instance_name:
        bucket = get_default_bucket_name(instance_name, project_id)
        prefix = get_default_state_prefix(instance_name)
        return f"gs://{bucket}/{prefix}/default.tfstate"

    return None


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
    gcs_uri: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Downloads and parses Terraform outputs directly from GCS remote state."""
    bucket_name, blob_name = _parse_gcs_uri(gcs_uri)
    content = _download_gcs_blob_text(bucket_name, blob_name, project_id)
    return _parse_terraform_state_outputs(content, gcs_uri)


def _get_outputs_from_local() -> dict[str, Any]:
    """Runs `terraform output -json` locally or parses local terraform.tfstate directly if present."""
    local_state_file = Path("terraform.tfstate")
    if local_state_file.is_file():
        with contextlib.suppress(OSError, click.ClickException):
            return _parse_terraform_state_outputs(
                local_state_file.read_text(encoding="utf-8"),
                source_description=str(local_state_file.resolve()),
            )

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
    project_id: str | None = None,
    instance_name: str | None = None,
    tf_state_location: str | None = None,
) -> TerraformOutputs:
    """Fetches, parses, and validates deployment outputs into an immutable TerraformOutputs dataclass."""
    gcs_uri = _resolve_remote_state_gcs_uri(
        project_id=project_id,
        instance_name=instance_name,
        tf_state_location=tf_state_location,
    )
    raw_outputs = (
        _get_outputs_from_gcs(gcs_uri, project_id)
        if gcs_uri
        else _get_outputs_from_local()
    )
    return TerraformOutputs.from_state_outputs(raw_outputs)
