# =============================================================================
# INGESTION HELPER SERVICE MODULE - UNIT TEST SUITE (service.tftest.hcl)
# =============================================================================
#
# PURPOSE:
# This test suite hermetically validates the contract of the ingestion helper_service
# module without requiring GCP credentials or network access.
#
# ARCHITECTURAL SCENARIOS TESTED:
#   1. Baseline Service Contract   - Image, internal ingress, timeout, storage & dataflow IAM
#   2. Instance Name Prefixing     - Resource naming & service account account_id prefix
#   3. Storage: Spanner Disabled   - try() fallbacks to empty strings, zero Spanner IAM
#   4. Storage: Spanner Enabled    - Spanner databaseUser IAM & container env vars
#   5. Redis Secret Injection      - Secret Manager accessor IAM & REDIS_PASSWORD env
#   6. Network: Direct VPC Egress  - Subnetwork interface, tags, and egress mode
#
# DEVELOPER GUIDE: HOW TO EXTEND THIS TEST SUITE
#   - Each `run` block tests a SINGLE scenario using `command = plan`.
#   - Do NOT repeat baseline variables; inherit from the root `variables {}` block
#     and only override the specific attribute under test in `run.variables {}`.
#   - Always write human-readable, descriptive `error_message` strings explaining
#     the exact invariant that failed.
# =============================================================================

mock_provider "google" {}

# -----------------------------------------------------------------------------
# Canonical Baseline Configuration (Inherited by all test runs)
# -----------------------------------------------------------------------------
variables {
  project_id                    = "test-project"
  instance_name                 = ""
  region                        = "us-central1"
  stateless_deletion_protection = false
  image                         = "gcr.io/test/ingestion-helper:latest"
  ingestion_bucket_name         = "test-ingestion-bucket"
  ingestion_artifacts_path      = "metadata"
  enable_embeddings_generation  = true
  spanner_config                = null
  vpc_access                    = null
  redis_auth_secret_id          = null
  redis_host                    = "10.0.0.5"
  redis_port                    = "6379"
}

# =============================================================================
# SCENARIO 1: Baseline Service Contract
# =============================================================================
run "baseline_service_contract" {
  command = plan

  # 1. Output & Container Image
  assert {
    condition     = output.image == "gcr.io/test/ingestion-helper:latest"
    error_message = "output.image must reflect the configured container image URI"
  }

  # 2. Internal Ingress & Timeout Security Contract
  assert {
    condition     = google_cloud_run_v2_service.ingestion_helper.ingress == "INGRESS_TRAFFIC_INTERNAL_ONLY"
    error_message = "Ingestion helper service must restrict ingress to internal VPC traffic only"
  }

  assert {
    condition     = google_cloud_run_v2_service.ingestion_helper.template[0].timeout == "1800s"
    error_message = "Ingestion helper service timeout must be configured to 1800s (30 minutes)"
  }

  # 3. Default Naming & Service Account Identity
  assert {
    condition     = google_service_account.helper_sa.account_id == "dc-ing-hlp-sa"
    error_message = "Service account account_id must default to dc-ing-hlp-sa when instance_name is empty"
  }

  assert {
    condition     = google_cloud_run_v2_service.ingestion_helper.name == "dc-ingestion-helper"
    error_message = "Cloud Run service name must default to dc-ingestion-helper when instance_name is empty"
  }

  # 4. Baseline IAM: Storage Admin & Dataflow Viewer
  assert {
    condition     = google_storage_bucket_iam_member.helper_bucket_access.role == "roles/storage.objectAdmin" && google_storage_bucket_iam_member.helper_bucket_access.bucket == "test-ingestion-bucket"
    error_message = "Storage objectAdmin role must be granted on the ingestion artifacts bucket"
  }

  assert {
    condition     = google_project_iam_member.helper_dataflow_viewer.role == "roles/dataflow.viewer"
    error_message = "roles/dataflow.viewer role must be granted for pipeline status inspection"
  }
}

# =============================================================================
# SCENARIO 2: Instance Name Prefixing
# =============================================================================
run "instance_name_prefixing" {
  command = plan

  variables {
    instance_name = "prod"
  }

  assert {
    condition     = google_cloud_run_v2_service.ingestion_helper.name == "prod-dc-ingestion-helper"
    error_message = "Cloud Run service name must be prefixed with instance_name"
  }

  assert {
    condition     = google_service_account.helper_sa.account_id == "prod-dc-ing-hlp-sa"
    error_message = "Service account account_id must be prefixed with instance_name"
  }
}

# =============================================================================
# SCENARIO 3: Storage - Spanner Disabled (try() fallbacks & zero IAM)
# =============================================================================
run "spanner_disabled_fallback" {
  command = plan

  variables {
    spanner_config = null
  }

  assert {
    condition     = length(google_spanner_database_iam_member.helper_spanner_user) == 0
    error_message = "Database User IAM binding must NOT be created when spanner_config is null"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "SPANNER_INSTANCE_ID"]) == ""
    error_message = "SPANNER_INSTANCE_ID must fall back to empty string via try() when spanner_config is null"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "SPANNER_DATABASE_ID"]) == ""
    error_message = "SPANNER_DATABASE_ID must fall back to empty string via try() when spanner_config is null"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "SPANNER_GRAPH_DATABASE_ID"]) == ""
    error_message = "SPANNER_GRAPH_DATABASE_ID must fall back to empty string via try() when spanner_config is null"
  }
}

# =============================================================================
# SCENARIO 4: Storage - Spanner Enabled (databaseUser IAM & container envs)
# =============================================================================
run "spanner_enabled" {
  command = plan

  variables {
    spanner_config = {
      instance_id = "test-spanner-instance"
      database_id = "test-spanner-db"
    }
  }

  assert {
    condition     = length(google_spanner_database_iam_member.helper_spanner_user) == 1
    error_message = "Database User IAM binding MUST be created when spanner_config is provided"
  }

  assert {
    condition     = google_spanner_database_iam_member.helper_spanner_user[0].role == "roles/spanner.databaseUser"
    error_message = "Spanner IAM role must be roles/spanner.databaseUser"
  }

  assert {
    condition     = google_spanner_database_iam_member.helper_spanner_user[0].instance == "test-spanner-instance" && google_spanner_database_iam_member.helper_spanner_user[0].database == "test-spanner-db"
    error_message = "Spanner IAM member must target configured instance and database"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "SPANNER_INSTANCE_ID"]) == "test-spanner-instance"
    error_message = "SPANNER_INSTANCE_ID must match spanner_config.instance_id"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.value if e.name == "SPANNER_DATABASE_ID"]) == "test-spanner-db"
    error_message = "SPANNER_DATABASE_ID must match spanner_config.database_id"
  }
}

# =============================================================================
# SCENARIO 5: Redis - Secret Manager Access & Env Injection
# =============================================================================
run "redis_secret_injection" {
  command = plan

  variables {
    redis_auth_secret_id = "custom-redis-secret"
  }

  assert {
    condition     = length(google_secret_manager_secret_iam_member.helper_redis_auth_secret_accessor) == 1
    error_message = "Secret accessor IAM binding must be created when redis_auth_secret_id is provided"
  }

  assert {
    condition     = google_secret_manager_secret_iam_member.helper_redis_auth_secret_accessor[0].secret_id == "custom-redis-secret"
    error_message = "Secret accessor IAM binding must target the configured redis_auth_secret_id"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].env : e.name if e.name == "REDIS_PASSWORD"]) == "REDIS_PASSWORD"
    error_message = "Container env list must include REDIS_PASSWORD when secret is configured"
  }
}

# =============================================================================
# SCENARIO 6: Network Perimeter - Direct VPC Egress
# =============================================================================
run "with_vpc_egress" {
  command = plan

  variables {
    vpc_access = {
      network_id      = "projects/test-project/global/networks/test-vpc"
      subnet_id       = "projects/test-project/regions/us-central1/subnetworks/test-sub"
      vpc_egress_mode = "PRIVATE_RANGES_ONLY"
    }
  }

  assert {
    condition     = length(google_cloud_run_v2_service.ingestion_helper.template[0].vpc_access) == 1
    error_message = "vpc_access block must be generated when vpc_access is configured"
  }

  assert {
    condition     = google_cloud_run_v2_service.ingestion_helper.template[0].vpc_access[0].egress == "PRIVATE_RANGES_ONLY"
    error_message = "VPC egress mode must match configured vpc_egress_mode"
  }

  assert {
    condition     = google_cloud_run_v2_service.ingestion_helper.template[0].vpc_access[0].network_interfaces[0].network == "projects/test-project/global/networks/test-vpc"
    error_message = "VPC network interface must match configured network_id"
  }
}
