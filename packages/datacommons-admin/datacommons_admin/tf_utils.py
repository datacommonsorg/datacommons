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


def get_terraform_output(key: str) -> str:
    """Fetches a specific key from `terraform output -json` with graceful error handling."""
    if not shutil.which("terraform"):
        raise click.ClickException(
            "Terraform CLI not found. Please ensure Terraform is installed and available in your PATH."
        )

    try:
        result = subprocess.run(
            ["terraform", "output", "-json"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise click.ClickException(
            f"Failed to run 'terraform output'. Are you in an initialized Terraform deployment directory?\n"
            f"Error details: {e.stderr.strip() or e.stdout.strip()}"
        ) from e

    try:
        outputs = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise click.ClickException(
            "Failed to parse 'terraform output -json'. The output was not valid JSON."
        ) from e

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
                f"No Terraform outputs found in '{cwd}'.\n"
                "Please navigate to your initialized DCP Terraform directory (e.g., 'cd my-namespace') and ensure 'terraform apply' has been run."
            )
        raise click.ClickException(
            f"No Terraform outputs found in '{cwd}'.\n"
            "Please ensure you have successfully run 'terraform apply' to generate the deployment state."
        )

    if key not in outputs:
        from pathlib import Path

        raise click.ClickException(
            f"Terraform output key '{key}' not found in '{Path.cwd()}'.\n"
            "Please verify that your Terraform configuration exports this output and that 'terraform apply' was fully completed."
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


def get_tfvars_api_key() -> str | None:
    """Parses `terraform.tfvars` in the current working directory and returns the Data Commons API key if defined."""
    from pathlib import Path

    tfvars_path = Path.cwd() / "terraform.tfvars"
    if not tfvars_path.exists():
        return None

    try:
        content = tfvars_path.read_text()
        for raw_line in content.splitlines():
            # Strip inline comments (e.g., # or //)
            line = raw_line.split("#", 1)[0].split("//", 1)[0].strip()
            if not line:
                continue
            if "=" in line:
                parts = line.split("=", 1)
                k = parts[0].strip()
                v = parts[1].strip()
                if (v.startswith('"') and v.endswith('"')) or (
                    v.startswith("'") and v.endswith("'")
                ):
                    v = v[1:-1].strip()
                if k in ["auth_google_datacommons_api_key", "dc_api_key"]:
                    return v
    except (OSError, ValueError):
        return None
    return None
