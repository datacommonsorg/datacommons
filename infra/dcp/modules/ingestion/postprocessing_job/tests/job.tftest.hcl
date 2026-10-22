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

# Unit tests for the ingestion postprocessing_job module (infra/dcp/modules/ingestion/postprocessing_job/main.tf).
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
  project_id                     = "test-project"
  instance_name                  = ""
  region                         = "us-central1"
  stateless_deletion_protection  = false
  image                          = "gcr.io/test/postprocessing-job:latest"
  cpu                            = "2"
  memory                         = "4Gi"
  timeout                        = "3600s"
  vpc_access                     = null
  enable_bigquery_postprocessing = false
  enable_embeddings_generation   = false
  spanner_config = {
    instance_id                = "test-spanner-instance"
    database_id                = "test-spanner-db"
    enable_bigquery_connection = false
    bigquery_connection_id     = ""
  }
}

# -----------------------------------------------------------------------------
# Run 1: Default Configuration (optional features disabled / empty)
# -----------------------------------------------------------------------------
run "default_configuration" {
  command = plan

  # When instance_name is "", resource names should not have a leading "<instance_name>-" prefix.
  assert {
    condition     = output.job_name == "dc-ingestion-postprocessing-job" && google_service_account.postprocessing_sa.account_id == "dc-ing-pst-sa"
    error_message = "Job and service account names must be unprefixed when instance_name is empty"
  }

  # When vpc_access is null, no Direct VPC Egress block should be attached to the Cloud Run Job.
  assert {
    condition     = length(google_cloud_run_v2_job.dc_postprocessing_job.template[0].template[0].vpc_access) == 0
    error_message = "vpc_access block must not be created when vpc_access is null"
  }

  # Baseline environment contract: ensures required container env vars and defaults are present.
  assert {
    condition = {
      for e in google_cloud_run_v2_job.dc_postprocessing_job.template[0].template[0].containers[0].env :
      e.name => e.value
      } == {
      PROJECT_ID          = "test-project"
      SPANNER_PROJECT_ID  = "test-project"
      SPANNER_INSTANCE_ID = "test-spanner-instance"
      SPANNER_DATABASE_ID = "test-spanner-db"
      BQ_SPANNER_CONN_ID  = ""
      LOCATION            = "us-central1"
      ENABLE_EMBEDDINGS   = "false"
    }
    error_message = "Baseline container environment variables must match the expected contract"
  }

  # The postprocessing service account always requires Spanner Database User,
  # while BigQuery and Spanner instance viewer IAM bindings must be omitted when BigQuery postprocessing is disabled.
  assert {
    condition = (
      google_spanner_database_iam_member.postprocessing_spanner_user.role == "roles/spanner.databaseUser" &&
      length(google_project_iam_member.postprocessing_bq_job_user) == 0 &&
      length(google_spanner_instance_iam_member.postprocessing_spanner_instance_viewer) == 0 &&
      length(google_bigquery_connection_iam_member.postprocessing_bq_connection_user) == 0
    )
    error_message = "Only spanner.databaseUser IAM binding should be created when enable_bigquery_postprocessing is false"
  }
}

# -----------------------------------------------------------------------------
# Run 2: Custom Configuration (optional features enabled / populated)
# -----------------------------------------------------------------------------
run "custom_configuration" {
  command = plan

  variables {
    instance_name                  = "prod"
    enable_bigquery_postprocessing = true
    enable_embeddings_generation   = true
    vpc_access = {
      network_id      = "projects/test-project/global/networks/test-vpc"
      subnet_id       = "projects/test-project/regions/us-central1/subnetworks/test-sub"
      vpc_egress_mode = "ALL_TRAFFIC"
    }
    spanner_config = {
      instance_id                = "test-spanner-instance"
      database_id                = "test-spanner-db"
      enable_bigquery_connection = true
      bigquery_connection_id     = "prod_dc_conn"
    }
  }

  # When instance_name is set ("prod"), prefix both the Cloud Run job name and service account ID.
  assert {
    condition     = output.job_name == "prod-dc-ingestion-postprocessing-job" && google_service_account.postprocessing_sa.account_id == "prod-dc-ing-pst-sa"
    error_message = "Job name and service account ID must be prefixed with instance_name"
  }

  # When enable_embeddings_generation is true and bigquery_connection_id is set, update their env vars accordingly.
  assert {
    condition = (
      one([for e in google_cloud_run_v2_job.dc_postprocessing_job.template[0].template[0].containers[0].env : e.value if e.name == "ENABLE_EMBEDDINGS"]) == "true" &&
      one([for e in google_cloud_run_v2_job.dc_postprocessing_job.template[0].template[0].containers[0].env : e.value if e.name == "BQ_SPANNER_CONN_ID"]) == "prod_dc_conn"
    )
    error_message = "ENABLE_EMBEDDINGS must be 'true' and BQ_SPANNER_CONN_ID must reflect spanner_config.bigquery_connection_id"
  }

  # When vpc_access is provided, attach Direct VPC Egress with network, subnet, dcp-job tag, and egress mode.
  assert {
    condition = (
      length(google_cloud_run_v2_job.dc_postprocessing_job.template[0].template[0].vpc_access) == 1 &&
      google_cloud_run_v2_job.dc_postprocessing_job.template[0].template[0].vpc_access[0].egress == "ALL_TRAFFIC" &&
      google_cloud_run_v2_job.dc_postprocessing_job.template[0].template[0].vpc_access[0].network_interfaces[0].network == "projects/test-project/global/networks/test-vpc" &&
      google_cloud_run_v2_job.dc_postprocessing_job.template[0].template[0].vpc_access[0].network_interfaces[0].subnetwork == "projects/test-project/regions/us-central1/subnetworks/test-sub" &&
      google_cloud_run_v2_job.dc_postprocessing_job.template[0].template[0].vpc_access[0].network_interfaces[0].tags == tolist(["dcp-job"])
    )
    error_message = "VPC access block must configure network, subnetwork, dcp-job tag, and egress mode"
  }

  # When both enable_bigquery_postprocessing and spanner_config.enable_bigquery_connection are true,
  # grant BigQuery jobUser, Spanner instance viewer, and BigQuery connectionUser IAM roles.
  assert {
    condition = (
      length(google_project_iam_member.postprocessing_bq_job_user) == 1 &&
      google_project_iam_member.postprocessing_bq_job_user[0].role == "roles/bigquery.jobUser" &&
      length(google_spanner_instance_iam_member.postprocessing_spanner_instance_viewer) == 1 &&
      google_spanner_instance_iam_member.postprocessing_spanner_instance_viewer[0].instance == "test-spanner-instance" &&
      google_spanner_instance_iam_member.postprocessing_spanner_instance_viewer[0].role == "roles/spanner.viewer" &&
      length(google_bigquery_connection_iam_member.postprocessing_bq_connection_user) == 1 &&
      google_bigquery_connection_iam_member.postprocessing_bq_connection_user[0].connection_id == "prod_dc_conn" &&
      google_bigquery_connection_iam_member.postprocessing_bq_connection_user[0].role == "roles/bigquery.connectionUser"
    )
    error_message = "All BigQuery and Spanner instance IAM bindings must be created when BigQuery postprocessing and federation are enabled"
  }
}
