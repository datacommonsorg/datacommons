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

# Unit tests for the datacommons_services module (infra/dcp/modules/datacommons_services/main.tf).
#
# How this file works:
#   - `mock_provider "google" {}` stubs out the Google Cloud provider so `terraform test`
#     can run `terraform plan` offline without GCP credentials.
#   - The top-level `variables {}` block supplies required module inputs with all
#     optional features turned off. Every `run` block inherits these values by default.
#   - Run 1 (`default_configuration`) checks the planned resources when optional features are off.
#   - Run 2 (`custom_configuration`) overrides those inputs to turn optional features on
#     and checks that the corresponding resources, IAM bindings, and env vars are created.

mock_provider "google" {}

variables {
  project_id                    = "test-project"
  instance_name                 = ""
  region                        = "us-central1"
  stateless_deletion_protection = false
  image                         = "gcr.io/test/image:latest"
  cpu                           = "4"
  memory                        = "16G"
  min_instances                 = 1
  max_instances                 = 3
  make_public                   = false
  mcp_search_scope              = "custom_only"
  env_vars                      = []
  secret_env_vars               = []
  spanner_config = {
    instance_id = "test-spanner-instance"
    database_id = "test-spanner-db"
  }
  vpc_access = null
}

# -----------------------------------------------------------------------------
# Run 1: Default Configuration (optional features disabled / empty)
# -----------------------------------------------------------------------------
run "default_configuration" {
  command = plan

  # When instance_name is "", resource names should not have a leading "<instance_name>-" prefix.
  assert {
    condition     = output.service_name == "dc-datacommons-service" && google_service_account.serving_sa.account_id == "dc-srvs-sa"
    error_message = "Service and service account names must be unprefixed when instance_name is empty"
  }

  # When make_public is false, the Cloud Run service must stay private (no allUsers IAM binding).
  assert {
    condition     = length(google_cloud_run_v2_service_iam_member.public_access) == 0
    error_message = "Public invoker binding must not be created when make_public = false"
  }

  # When vpc_access is null, no Direct VPC Egress block should be attached to Cloud Run.
  assert {
    condition     = length(google_cloud_run_v2_service.dc_web_service.template[0].vpc_access) == 0
    error_message = "vpc_access block must not be created when vpc_access is null"
  }

  # When secret_env_vars is empty, no Secret Manager IAM bindings should be created.
  assert {
    condition     = length(google_secret_manager_secret_iam_member.serving_secret_accessor) == 0
    error_message = "No secret accessor IAM bindings should be created when secret_env_vars is empty"
  }

  # The serving service account always requires VPC Access, Vertex AI, and Spanner Reader IAM roles.
  assert {
    condition = (
      contains(keys(google_project_iam_member.serving_sa_roles), "roles/vpcaccess.user") &&
      contains(keys(google_project_iam_member.serving_sa_roles), "roles/aiplatform.user") &&
      google_spanner_database_iam_member.serving_spanner_reader.role == "roles/spanner.databaseReader"
    )
    error_message = "Serving service account must be granted vpcaccess.user, aiplatform.user, and spanner.databaseReader"
  }

  # Unset optional variables (google_analytics_tag_id, mcp_instructions_path) must become "".
  assert {
    condition     = one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.value if e.name == "GOOGLE_ANALYTICS_TAG_ID"]) == ""
    error_message = "GOOGLE_ANALYTICS_TAG_ID must default to an empty string when google_analytics_tag_id is null"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.value if e.name == "DC_INSTRUCTIONS_DIR"]) == ""
    error_message = "DC_INSTRUCTIONS_DIR must default to an empty string when mcp_instructions_path is null"
  }
}

# -----------------------------------------------------------------------------
# Run 2: Custom Configuration (optional features enabled / populated)
# -----------------------------------------------------------------------------
run "custom_configuration" {
  command = plan

  variables {
    instance_name           = "prod"
    make_public             = true
    google_analytics_tag_id = "G-TEST1234"
    artifacts_bucket_name   = "test-artifacts-bucket"
    mcp_instructions_path   = "mcp/custom-instructions"
    vpc_access = {
      network_id      = "projects/test-project/global/networks/test-vpc"
      subnet_id       = "projects/test-project/regions/us-central1/subnetworks/test-sub"
      vpc_egress_mode = "ALL_TRAFFIC"
    }
    env_vars = [
      {
        name  = "CUSTOM_ENV_VAR"
        value = "custom-val"
      }
    ]
    secret_env_vars = [
      {
        name    = "CUSTOM_SECRET_KEY"
        secret  = "my-secret-id"
        version = "latest"
      }
    ]
  }

  # When instance_name is set ("prod"), prefix both the Cloud Run service name and service account ID.
  assert {
    condition     = output.service_name == "prod-dc-datacommons-service" && google_service_account.serving_sa.account_id == "prod-dc-srvs-sa"
    error_message = "Service name and service account ID must be prefixed with instance_name"
  }

  # When make_public is true, grant allUsers the Cloud Run Invoker role.
  assert {
    condition = (
      length(google_cloud_run_v2_service_iam_member.public_access) == 1 &&
      google_cloud_run_v2_service_iam_member.public_access[0].role == "roles/run.invoker" &&
      google_cloud_run_v2_service_iam_member.public_access[0].member == "allUsers"
    )
    error_message = "Public invoker binding must grant roles/run.invoker to allUsers when make_public = true"
  }

  # When vpc_access is provided, attach Direct VPC Egress with network, subnet, tag, and egress mode.
  assert {
    condition = (
      length(google_cloud_run_v2_service.dc_web_service.template[0].vpc_access) == 1 &&
      google_cloud_run_v2_service.dc_web_service.template[0].vpc_access[0].egress == "ALL_TRAFFIC" &&
      google_cloud_run_v2_service.dc_web_service.template[0].vpc_access[0].network_interfaces[0].network == "projects/test-project/global/networks/test-vpc" &&
      google_cloud_run_v2_service.dc_web_service.template[0].vpc_access[0].network_interfaces[0].subnetwork == "projects/test-project/regions/us-central1/subnetworks/test-sub" &&
      google_cloud_run_v2_service.dc_web_service.template[0].vpc_access[0].network_interfaces[0].tags == tolist(["dcp-service"])
    )
    error_message = "VPC access block must configure network, subnetwork, dcp-service tag, and egress mode"
  }

  # Entries in env_vars must be added as plain container environment variables.
  assert {
    condition     = one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.value if e.name == "CUSTOM_ENV_VAR"]) == "custom-val"
    error_message = "Dynamic env block must inject variables from var.env_vars"
  }

  # Entries in secret_env_vars must both (1) grant the service account Secret Accessor IAM on the secret
  # and (2) mount the secret reference onto the Cloud Run container.
  assert {
    condition = (
      contains(keys(google_secret_manager_secret_iam_member.serving_secret_accessor), "CUSTOM_SECRET_KEY") &&
      google_secret_manager_secret_iam_member.serving_secret_accessor["CUSTOM_SECRET_KEY"].secret_id == "my-secret-id" &&
      google_secret_manager_secret_iam_member.serving_secret_accessor["CUSTOM_SECRET_KEY"].role == "roles/secretmanager.secretAccessor"
    )
    error_message = "Secret accessor IAM binding must grant roles/secretmanager.secretAccessor on the target secret_id"
  }

  assert {
    condition = (
      one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.value_source[0].secret_key_ref[0].secret if e.name == "CUSTOM_SECRET_KEY"]) == "my-secret-id" &&
      one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.value_source[0].secret_key_ref[0].version if e.name == "CUSTOM_SECRET_KEY"]) == "latest"
    )
    error_message = "Container env CUSTOM_SECRET_KEY must inject secret_key_ref targeting my-secret-id@latest"
  }

  # When optional strings are set, populate their container env vars.
  assert {
    condition     = one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.value if e.name == "GOOGLE_ANALYTICS_TAG_ID"]) == "G-TEST1234"
    error_message = "GOOGLE_ANALYTICS_TAG_ID must reflect google_analytics_tag_id when provided"
  }

  # When mcp_instructions_path is set, combine artifacts_bucket_name and mcp_instructions_path into a gs:// URI.
  assert {
    condition     = one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.value if e.name == "DC_INSTRUCTIONS_DIR"]) == "gs://test-artifacts-bucket/mcp/custom-instructions"
    error_message = "DC_INSTRUCTIONS_DIR must construct a gs:// URI from artifacts_bucket_name and mcp_instructions_path"
  }
}
