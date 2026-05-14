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


TF_OUTPUT_INGESTION_HELPER_URI = "dcp_ingestion_helper_uri"
TF_OUTPUT_ORCHESTRATOR_SERVICE_ACCOUNT_EMAIL = "dcp_orchestrator_service_account_email"
TF_OUTPUT_SPANNER_INSTANCE_ID = "dcp_spanner_instance_id"
TF_OUTPUT_SPANNER_DATABASE_ID = "dcp_spanner_database_id"


def get_terraform_output(key: str) -> str:
    """Fetches a specific key from `terraform output -json` with graceful error handling."""
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
            f"Failed to run 'terraform output'. Are you in an initialized Terraform deployment directory?\n"
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
                f"No Terraform outputs found in '{cwd}'.\n"
                "Please navigate to your initialized DCP Terraform directory (e.g., 'cd my-namespace') and ensure 'terraform apply' has been run."
            )
        else:
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


def get_dcp_ingestion_helper_uri() -> str:
    """Convenience wrapper to fetch the dcp_ingestion_helper_uri Terraform output."""
    return get_terraform_output(TF_OUTPUT_INGESTION_HELPER_URI)


def get_dcp_orchestrator_service_account_email() -> str:
    """Convenience wrapper to fetch the dcp_orchestrator_service_account_email Terraform output."""
    return get_terraform_output(TF_OUTPUT_ORCHESTRATOR_SERVICE_ACCOUNT_EMAIL)


def get_dcp_spanner_instance_id() -> str:
    """Convenience wrapper to fetch the dcp_spanner_instance_id Terraform output."""
    return get_terraform_output(TF_OUTPUT_SPANNER_INSTANCE_ID)


def get_dcp_spanner_database_id() -> str:
    """Convenience wrapper to fetch the dcp_spanner_database_id Terraform output."""
    return get_terraform_output(TF_OUTPUT_SPANNER_DATABASE_ID)
