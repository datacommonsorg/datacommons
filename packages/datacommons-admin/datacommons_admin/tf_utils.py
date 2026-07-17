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
TF_OUTPUT_DATACOMMONS_SERVICE_URL = "datacommons_service_url"


def _get_outputs_from_gcs(
    tf_state_location: str | None,
    project_id: str | None,
    instance_name: str | None,
) -> dict:
    from google.cloud import storage
    from google.cloud.exceptions import GoogleCloudError

    # Resolve the GCS URI
    if tf_state_location:
        gcs_uri = tf_state_location.strip()
        if not gcs_uri.endswith(".tfstate"):
            gcs_uri = gcs_uri.rstrip("/") + "/default.tfstate"
    elif project_id and instance_name:
        p_id = project_id.strip()
        i_name = instance_name.strip()
        gcs_uri = f"gs://tf-state-{i_name}-{p_id}/terraform/state/{i_name}/default.tfstate"
    else:
        return {}

    try:
        if not gcs_uri.startswith("gs://"):
            raise click.ClickException(f"Invalid GCS URI '{gcs_uri}'. Must start with 'gs://'.")
        parts = gcs_uri[5:].split("/", 1)
        if len(parts) < 2 or not parts[1]:
            raise click.ClickException(f"Invalid GCS URI '{gcs_uri}'. Must specify bucket and object path.")
        bucket_name, blob_name = parts[0], parts[1]

        try:
            client = storage.Client()
        except Exception as e:
            raise click.ClickException(
                f"Failed to initialize Google Cloud Storage client: {e}.\n"
                "Please ensure you are authenticated via 'gcloud auth application-default login'."
            )

        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        try:
            content = blob.download_as_text()
        except GoogleCloudError as e:
            if "404" in str(e) or "Not Found" in str(e):
                raise click.ClickException(
                    f"Terraform state file not found at '{gcs_uri}'.\n"
                    "Please verify that the --project-id, --instance-name, or --tf-state-location flags are correct and that resources were deployed."
                )
            raise click.ClickException(
                f"Failed to download Terraform state from GCS at '{gcs_uri}': {e}"
            )

        try:
            state_data = json.loads(content)
        except json.JSONDecodeError:
            raise click.ClickException(f"Failed to parse Terraform state at '{gcs_uri}' as valid JSON.")

        outputs = state_data.get("outputs", {})
        if not outputs:
            raise click.ClickException(
                f"No outputs found in the Terraform state file at '{gcs_uri}'.\n"
                "Please verify that your deployment is active and that variables are exported."
            )
        return outputs

    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"An unexpected error occurred while fetching remote state: {e}")


def get_terraform_output(key: str) -> str:
    """Fetches a specific key from `terraform output -json` (local or remote GCS state)."""
    ctx = click.get_current_context(silent=True)
    project_id = None
    instance_name = None
    tf_state_location = None

    if ctx and ctx.obj:
        cur_ctx = ctx
        while cur_ctx:
            if cur_ctx.obj:
                project_id = project_id or cur_ctx.obj.get("project_id")
                instance_name = instance_name or cur_ctx.obj.get("instance_name")
                tf_state_location = tf_state_location or cur_ctx.obj.get("tf_state_location")
            cur_ctx = cur_ctx.parent

    use_remote = bool(tf_state_location or (project_id and instance_name))

    if use_remote:
        outputs = _get_outputs_from_gcs(tf_state_location, project_id, instance_name)
    else:
        if not shutil.which("terraform"):
            raise click.ClickException(
                "Terraform CLI not found. Please ensure Terraform is installed and available in your PATH."
            )

        try:
            result = subprocess.run(
                ["terraform", "output", "-json"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise click.ClickException(
                f"Failed to run 'terraform output'.\n"
                f"To resolve your deployment configuration, either:\n"
                f"a. Run this command inside your initialized DCP Terraform deployment directory (where 'terraform apply' has been run).\n"
                f"b. Specify the GCS remote state flags on the 'admin' group: --project-id <id> and --instance-name <name> (or --tf-state-location <gcs_uri>).\n\n"
                f"Error details: {e.stderr.strip() or e.stdout.strip()}"
            )

        try:
            outputs = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise click.ClickException(
                "Failed to parse 'terraform output -json'. The output was not valid JSON."
            )

        if not outputs:
            from pathlib import Path

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
            else:
                raise click.ClickException(
                    f"No Terraform outputs found in '{cwd}'.\n"
                    "Please ensure you have successfully run 'terraform apply' to generate the deployment state."
                )

    if key not in outputs:
        from pathlib import Path
        location_desc = tf_state_location or f"GCP project: '{project_id}' / instance: '{instance_name}'" if use_remote else f"'{Path.cwd()}'"
        raise click.ClickException(
            f"Terraform output key '{key}' not found in {location_desc}.\n"
            "Please verify that your Terraform configuration exports this output."
        )

    value = outputs[key].get("value")
    if not value:
        raise click.ClickException(
            f"Terraform output '{key}' is empty or null. Please verify your deployment state."
        )

    return str(value)


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


def get_datacommons_service_url() -> str:
    """Convenience wrapper to fetch the datacommons_service_url Terraform output."""
    return get_terraform_output(TF_OUTPUT_DATACOMMONS_SERVICE_URL)
