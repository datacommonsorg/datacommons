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
  cdc_data_job_timeout               = var.cdc_data_job_timeout
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

variable "cdc_data_job_timeout" {{
  description = "Docker container timeout for the CDC data ingestion job"
  type        = string
  default     = "3600s"
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

output "dcp_orchestrator_service_account_email" {{
  value = module.datacommons_dcp.dcp_orchestrator_service_account_email
}}

output "data_bucket_name" {{
  value = module.datacommons_dcp.data_bucket_name
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

# Optional CDC Data Job timeout (defaults to 3600s)
# cdc_data_job_timeout = "3600s"
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
