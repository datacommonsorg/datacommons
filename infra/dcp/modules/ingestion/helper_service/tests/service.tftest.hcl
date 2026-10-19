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

# Unit tests for the ingestion helper_service module (infra/dcp/modules/ingestion/helper_service/main.tf).
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
  image                         = "gcr.io/test/ingestion-helper:latest"
  ingestion_bucket_name         = "test-ingestion-bucket"
  ingestion_artifacts_path      = "metadata"
  enable_embeddings_generation  = false
  spanner_config = {
    instance_id = "test-spanner-instance"
    database_id = "test-spanner-db"
  }
  spanner_version_retention_period = "24h"
  vpc_access                       = null
  redis_config                     = null
}

# -----------------------------------------------------------------------------
# Run 1: Default Configuration (optional features disabled / empty)
# -----------------------------------------------------------------------------
run "default_configuration" {
  command = plan

  # When instance_name is "", resource names should not have a leading "<instance_name>-" prefix.
  assert {
    condition     = output.service_name == "dc-ingestion-helper" && google_service_account.helper_sa.account_id == "dc-ing-hlp-sa"
    error_message = "Service and service account names must be unprefixed when instance_name is empty"
  }

  # When vpc_access is null, no Direct VPC Egress block should be attached to Cloud Run.
  assert {
    condition     = length(google_cloud_run_v2_service.ingestion_helper.template[0].vpc_access) == 0
    error_message = "vpc_access block must not be created when vpc_access is null"
  }

  # The helper service account always requires Spanner Database User, Storage Object Admin, and Dataflow Viewer IAM roles.
  assert {
    condition = (
      google_spanner_database_iam_member.helper_spanner_user.role == "roles/spanner.databaseUser" &&
      google_storage_bucket_iam_member.helper_bucket_access.role == "roles/storage.objectAdmin" &&
      google_project_iam_member.helper_dataflow_viewer.role == "roles/dataflow.viewer"
    )
    error_message = "Helper service account must be granted spanner.databaseUser, storage.objectAdmin, and dataflow.viewer"
  }

  # When enable_embeddings_generation is false, ENABLE_EMBEDDINGS must be "false".
  assert {
    condition     = one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "ENABLE_EMBEDDINGS"]) == "false"
    error_message = "ENABLE_EMBEDDINGS must be 'false' when enable_embeddings_generation = false"
  }

  # When redis_config is null, no Secret Manager IAM binding or REDIS_PASSWORD env var should be created,
  # and Redis env vars must fall back to empty strings.
  assert {
    condition = (
      length(google_secret_manager_secret_iam_member.helper_redis_auth_secret_accessor) == 0 &&
      length([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.name if e.name == "REDIS_PASSWORD"]) == 0
    )
    error_message = "No Redis secret accessor IAM binding or REDIS_PASSWORD env var should be created when redis_config is null"
  }

  assert {
    condition = (
      one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "REDIS_HOST"]) == "" &&
      one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "REDIS_PORT"]) == "" &&
      one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "REDIS_CA_CERT"]) == ""
    )
    error_message = "REDIS_HOST, REDIS_PORT, and REDIS_CA_CERT must be empty when redis_config is null"
  }
}

# -----------------------------------------------------------------------------
# Run 2: Custom Configuration (optional features enabled / populated)
# -----------------------------------------------------------------------------
run "custom_configuration" {
  command = plan

  variables {
    instance_name                = "prod"
    enable_embeddings_generation = true
    vpc_access = {
      network_id      = "projects/test-project/global/networks/test-vpc"
      subnet_id       = "projects/test-project/regions/us-central1/subnetworks/test-sub"
      vpc_egress_mode = "ALL_TRAFFIC"
    }
    redis_config = {
      host           = "10.0.0.8"
      port           = "6380"
      auth_secret_id = "custom-redis-secret"
      ca_cert        = "test-ca-cert-pem"
    }
  }

  # When instance_name is set ("prod"), prefix both the Cloud Run service name and service account ID.
  assert {
    condition     = output.service_name == "prod-dc-ingestion-helper" && google_service_account.helper_sa.account_id == "prod-dc-ing-hlp-sa"
    error_message = "Service name and service account ID must be prefixed with instance_name"
  }

  # When enable_embeddings_generation is true, ENABLE_EMBEDDINGS must be "true".
  assert {
    condition     = one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "ENABLE_EMBEDDINGS"]) == "true"
    error_message = "ENABLE_EMBEDDINGS must be 'true' when enable_embeddings_generation = true"
  }

  # When vpc_access is provided, attach Direct VPC Egress with network, subnet, tag, and egress mode.
  assert {
    condition = (
      length(google_cloud_run_v2_service.ingestion_helper.template[0].vpc_access) == 1 &&
      google_cloud_run_v2_service.ingestion_helper.template[0].vpc_access[0].egress == "ALL_TRAFFIC" &&
      google_cloud_run_v2_service.ingestion_helper.template[0].vpc_access[0].network_interfaces[0].network == "projects/test-project/global/networks/test-vpc" &&
      google_cloud_run_v2_service.ingestion_helper.template[0].vpc_access[0].network_interfaces[0].subnetwork == "projects/test-project/regions/us-central1/subnetworks/test-sub" &&
      google_cloud_run_v2_service.ingestion_helper.template[0].vpc_access[0].network_interfaces[0].tags == tolist(["dcp-service"])
    )
    error_message = "VPC access block must configure network, subnetwork, dcp-service tag, and egress mode"
  }

  # When redis_config is provided with auth_secret_id, grant Secret Accessor IAM on the secret,
  # mount REDIS_PASSWORD from Secret Manager, and populate REDIS_HOST, REDIS_PORT, and REDIS_CA_CERT.
  assert {
    condition = (
      length(google_secret_manager_secret_iam_member.helper_redis_auth_secret_accessor) == 1 &&
      google_secret_manager_secret_iam_member.helper_redis_auth_secret_accessor[0].secret_id == "custom-redis-secret" &&
      google_secret_manager_secret_iam_member.helper_redis_auth_secret_accessor[0].role == "roles/secretmanager.secretAccessor"
    )
    error_message = "Secret accessor IAM binding must grant roles/secretmanager.secretAccessor on redis_config.auth_secret_id"
  }

  assert {
    condition = (
      one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value_source[0].secret_key_ref[0].secret if e.name == "REDIS_PASSWORD"]) == "custom-redis-secret" &&
      one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value_source[0].secret_key_ref[0].version if e.name == "REDIS_PASSWORD"]) == "latest"
    )
    error_message = "Container env REDIS_PASSWORD must inject secret_key_ref targeting custom-redis-secret@latest"
  }

  assert {
    condition = (
      one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "REDIS_HOST"]) == "10.0.0.8" &&
      one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "REDIS_PORT"]) == "6380" &&
      one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "REDIS_CA_CERT"]) == "test-ca-cert-pem"
    )
    error_message = "REDIS_HOST, REDIS_PORT, and REDIS_CA_CERT must reflect redis_config values"
  }
}
