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

from pathlib import Path

import click
from google.api_core import exceptions
from google.cloud import storage

MAIN_TF_TEMPLATE = """terraform {{
  required_version = ">= 1.5.0"

  required_providers {{
    google = {{
      source  = "hashicorp/google"
      version = ">= 5.11.0"
    }}
  }}
}}

module "datacommons_dcp" {{
  # Pin this to a tag/commit for reproducible deployments.
  source = "git::https://github.com/datacommonsorg/datacommons.git//infra/dcp?ref={ref}"

  project_id = var.project_id
  namespace  = var.namespace
  cdc_dc_api_key = var.dc_api_key

  enable_dcp = true
  enable_cdc = true

  dcp_create_spanner_instance        = var.dcp_create_spanner_instance
  dcp_spanner_instance_id            = var.dcp_spanner_instance_id
  dcp_spanner_database_id            = var.dcp_spanner_database_id
  dcp_deploy_data_ingestion_workflow = var.dcp_deploy_data_ingestion_workflow
  dcp_ingestion_helper_image         = var.dcp_ingestion_helper_image
  cdc_gcs_data_bucket_input_folder   = var.gcs_data_bucket_input_folder
  cdc_data_job_image                 = var.cdc_data_job_image
}}

variable "project_id" {{
  description = "GCP project id"
  type        = string
}}

variable "namespace" {{
  description = "Prefix applied to provisioned resource names"
  type        = string
}}

variable "dc_api_key" {{
  description = "Data Commons API key"
  type        = string
  default     = ""
  sensitive   = true
}}

variable "dcp_create_spanner_instance" {{
  description = "Create a new Spanner instance for DCP"
  type        = bool
  default     = true
}}

variable "dcp_spanner_instance_id" {{
  description = "Spanner instance id for DCP"
  type        = string
  default     = ""
}}

variable "dcp_spanner_database_id" {{
  description = "Spanner database id for DCP"
  type        = string
  default     = "dcp-db"
}}

variable "dcp_deploy_data_ingestion_workflow" {{
  description = "Deploy the complete end-to-end Data Commons Ingestion workflow stack"
  type        = bool
  default     = true
}}

variable "dcp_ingestion_helper_image" {{
  description = "Docker image URL for the DCP ingestion helper service"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-ingestion-helper:latest"
}}

variable "gcs_data_bucket_input_folder" {{
  description = "GCS data bucket input folder for CDC"
  type        = string
  default     = "input"
}}

variable "cdc_data_job_image" {{
  description = "Docker image URL for the CDC data ingestion job"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-data:stable"
}}

output "dcp_service_url" {{
  value = module.datacommons_dcp.dcp_service_url
}}

output "dcp_spanner_instance_id" {{
  value = module.datacommons_dcp.dcp_spanner_instance_id
}}

output "dcp_spanner_database_id" {{
  value = module.datacommons_dcp.dcp_spanner_database_id
}}

output "dcp_ingestion_helper_uri" {{
  value = module.datacommons_dcp.dcp_ingestion_helper_uri
}}

output "cdc_service_url" {{
  value = module.datacommons_dcp.cdc_service_url
}}

output "cdc_data_job_name" {{
  value = module.datacommons_dcp.cdc_data_job_name
}}

output "workflow_name" {{
  value = module.datacommons_dcp.workflow_name
}}
"""

TFVARS_TEMPLATE = """project_id = "{project_id}"
namespace  = "{namespace}"
dc_api_key = "{dc_api_key}"

# Optional Spanner configuration (defaults to creating a new instance with dcp-db)
# dcp_create_spanner_instance = false
# dcp_spanner_instance_id     = "existing-instance-id"
dcp_spanner_database_id     = "dcp-db"

# Optional Ingestion Workflow configuration (defaults to true)
# dcp_deploy_data_ingestion_workflow = false
# dcp_ingestion_helper_image         = "gcr.io/datcom-ci/datacommons-ingestion-helper:latest"

# Optional GCS input folder (defaults to input)
# gcs_data_bucket_input_folder = "input"

# Optional CDC Data Job image (defaults to stable)
# cdc_data_job_image = "gcr.io/datcom-ci/datacommons-data:stable"
"""

REMOTE_STATE_TEMPLATE = """
## Remote State Management

Terraform state is configured to be stored remotely in Google Cloud Storage:
- **Bucket**: `gs://{bucket_name}`
- **Prefix**: `terraform/state`

This enables team collaboration, state locking, and automated pipeline deployments. The bucket is configured with Uniform Bucket-Level Access and object versioning.
"""

README_TEMPLATE = """# Data Commons Platform Terraform Setup

This directory contains Terraform configuration for a new Data Commons Platform instance.

Data Commons is an open knowledge graph for integrating and querying structured data across domains.
The Data Commons Platform is the deployable infrastructure stack that runs Data Commons services in your GCP project.
{remote_state_section}
## What This Terraform Creates

This setup deploys core Data Commons Platform infrastructure on GCP using the `infra/dcp` module, including Cloud Run services, Cloud Spanner resources, IAM bindings, and supporting service configuration.

## Configure Variables

Set environment-specific values in `terraform.tfvars` (for example `project_id`, `namespace`, and `dc_api_key`), and update module arguments in `main.tf` if you want to enable or tune additional features.

## Learn More About Variables

For the full list of supported module inputs and defaults, see:
- https://github.com/datacommonsorg/datacommons/blob/main/infra/dcp/variables.tf
- https://github.com/datacommonsorg/datacommons/blob/main/infra/dcp/terraform.tfvars.example
- https://github.com/datacommonsorg/datacommons/blob/main/infra/dcp/README.md

## Next Steps

1. Review `terraform.tfvars` and update values if needed.
2. Initialize Terraform:
   ```bash
   terraform init
   ```
3. Preview infrastructure changes:
   ```bash
   terraform plan
   ```
4. Deploy infrastructure:
   ```bash
   terraform apply
   ```

Generated using the Data Commons CLI tool:
https://github.com/datacommonsorg/datacommons
"""

BACKEND_TF_TEMPLATE = """terraform {{
  backend "gcs" {{
    bucket = "{bucket_name}"
    prefix = "terraform/state"
  }}
}}
"""


def _configure_remote_state(resolved_project_id: str, resolved_namespace: str) -> str:
    """Handles GCS state bucket verification, creation, and IAM setup."""
    default_bucket = f"tf-state-{resolved_namespace}-{resolved_project_id}"
    try:
        storage_client = storage.Client(project=resolved_project_id)
    except Exception as e:
        raise click.ClickException(
            f"Failed to initialize GCS client for project '{resolved_project_id}': {e}. "
            "Ensure you are authenticated via 'gcloud auth application-default login'."
        )

    while True:
        bucket_name = click.prompt(
            "Enter the name of your GCS Terraform State Bucket",
            type=str,
            default=default_bucket,
        ).strip()
        if not bucket_name:
            click.secho("Error: Bucket name cannot be empty.", fg="red")
            continue

        click.secho(f"Checking bucket gs://{bucket_name}...", fg="bright_black")
        try:
            bucket = storage_client.get_bucket(bucket_name)
            click.secho(f"Bucket gs://{bucket_name} already exists.", fg="yellow")
            reuse = click.confirm(
                f"Do you want to re-use the existing bucket gs://{bucket_name}?",
                default=True,
            )
            if reuse:
                return bucket_name
            else:
                click.secho(
                    "Please enter a different bucket name to continue.", fg="cyan"
                )
                continue
        except exceptions.NotFound:
            click.secho(
                f"Creating bucket gs://{bucket_name} in project {resolved_project_id}...",
                fg="bright_black",
            )
            try:
                new_bucket = storage_client.create_bucket(bucket_name, location="US")
                new_bucket.iam_configuration.uniform_bucket_level_access_enabled = True
                new_bucket.versioning_enabled = True
                new_bucket.patch()
                click.secho(
                    f"Enabling versioning on gs://{bucket_name}...", fg="bright_black"
                )

                click.secho(
                    "Configuring bucket IAM policy for project editors/owners...",
                    fg="bright_black",
                )
                policy = new_bucket.get_iam_policy(requested_policy_version=3)
                policy["roles/storage.objectAdmin"].add(
                    f"projectEditor:{resolved_project_id}"
                )
                policy["roles/storage.objectAdmin"].add(
                    f"projectOwner:{resolved_project_id}"
                )
                new_bucket.set_iam_policy(policy)

                return bucket_name
            except Exception as e:
                click.secho(
                    f"Error: Failed to create or access bucket gs://{bucket_name}.",
                    fg="red",
                    bold=True,
                )
                click.secho(str(e), fg="red")
                click.secho(
                    "Please verify permissions/names availability and try again.",
                    fg="yellow",
                )
                continue
        except Exception as e:
            click.secho(
                f"Error: Failed to access bucket gs://{bucket_name}.",
                fg="red",
                bold=True,
            )
            click.secho(str(e), fg="red")
            click.secho(
                "Please verify permissions/names availability and try again.",
                fg="yellow",
            )
            continue


@click.group()
def admin() -> None:
    """Admin commands."""


@admin.command()
@click.option(
    "--project-id", default="", help="GCP project id to initialize into tfvars."
)
@click.option(
    "--namespace", default="", help="Namespace prefix for provisioned resources."
)
@click.option("--dc-api-key", default="", help="Data Commons API key.")
@click.option(
    "--ref", default="main", show_default=True, help="Git ref for module source."
)
@click.option(
    "--force", is_flag=True, help="Overwrite existing generated files if present."
)
def init(
    project_id: str,
    namespace: str,
    dc_api_key: str,
    ref: str,
    force: bool,
) -> None:
    """Initialize Terraform scaffolding for Data Commons administration/infrastructure."""
    click.secho("Datacommons Admin Init", fg="cyan", bold=True)
    click.secho("Generating Terraform starter files...", fg="bright_black")

    resolved_project_id = (
        project_id.strip()
        or click.prompt("GCP project id", type=str, prompt_suffix=": ").strip()
    )
    if not resolved_project_id:
        raise click.ClickException("GCP project id must not be empty.")

    resolved_namespace = namespace.strip()
    while True:
        if not resolved_namespace:
            resolved_namespace = click.prompt(
                "Namespace", type=str, prompt_suffix=": "
            ).strip()
            if not resolved_namespace:
                click.secho("Error: Namespace must not be empty.", fg="red")
                continue

        target_dir = Path.cwd() / resolved_namespace
        if target_dir.exists() and not force:
            click.secho(
                f"Error: Folder '{resolved_namespace}' already exists locally. "
                "Please specify a different namespace, or use --force to overwrite.",
                fg="yellow",
            )
            resolved_namespace = ""
            continue

        break

    resolved_dc_api_key = (
        dc_api_key.strip()
        or click.prompt(
            "Data Commons API key (get one at apikeys.datacommons.org)",
            type=str,
            default="",
            show_default=False,
            prompt_suffix=": ",
        ).strip()
    )

    main_tf_path = target_dir / "main.tf"
    tfvars_path = target_dir / "terraform.tfvars"
    readme_path = target_dir / "README.md"
    backend_tf_path = target_dir / "backend.tf"

    use_remote_state = click.confirm(
        "Do you want to configure remote state storage in GCS?", default=False
    )

    paths_to_check = [main_tf_path, tfvars_path, readme_path]
    if use_remote_state:
        paths_to_check.append(backend_tf_path)

    existing_paths = [path for path in paths_to_check if path.exists()]
    if existing_paths and not force:
        existing_labels = ", ".join(str(path) for path in existing_paths)
        raise click.ClickException(
            f"Refusing to overwrite existing file(s): {existing_labels}. "
            "Use --force to overwrite."
        )

    resolved_bucket_name = (
        _configure_remote_state(resolved_project_id, resolved_namespace)
        if use_remote_state
        else ""
    )

    target_dir.mkdir(parents=True, exist_ok=True)
    main_tf_path.write_text(MAIN_TF_TEMPLATE.format(ref=ref), encoding="utf-8")
    tfvars_path.write_text(
        TFVARS_TEMPLATE.format(
            project_id=resolved_project_id,
            namespace=resolved_namespace,
            dc_api_key=resolved_dc_api_key,
        ),
        encoding="utf-8",
    )
    remote_state_info = ""
    if use_remote_state and resolved_bucket_name:
        remote_state_info = REMOTE_STATE_TEMPLATE.format(
            bucket_name=resolved_bucket_name
        )

    readme_path.write_text(
        README_TEMPLATE.format(remote_state_section=remote_state_info), encoding="utf-8"
    )
    if use_remote_state and resolved_bucket_name:
        backend_tf_path.write_text(
            BACKEND_TF_TEMPLATE.format(bucket_name=resolved_bucket_name),
            encoding="utf-8",
        )

    click.secho(f"Initialized Terraform scaffold in {target_dir}", fg="green")
    click.secho(f"- Wrote {main_tf_path}", fg="bright_black")
    click.secho(f"- Wrote {tfvars_path}", fg="bright_black")
    click.secho(f"- Wrote {readme_path}", fg="bright_black")
    if use_remote_state and resolved_bucket_name:
        click.secho(f"- Wrote {backend_tf_path}", fg="bright_black")
    click.secho(
        f"Generated new folder '{resolved_namespace}'. See {resolved_namespace}/README.md for next steps.",
        fg="cyan",
    )
