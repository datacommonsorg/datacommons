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

# Optional CDC search scope (defaults to base_and_custom)
# cdc_search_scope = "custom_only"
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
