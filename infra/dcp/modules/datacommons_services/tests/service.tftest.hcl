# =============================================================================
# DATA COMMONS SERVICES MODULE - UNIT TEST SUITE (service.tftest.hcl)
# =============================================================================
#
# PURPOSE:
# This test suite hermetically validates the contract of the datacommons_services
# module without requiring GCP credentials or network access.
#
# ARCHITECTURAL SCENARIOS TESTED:
#   1. Baseline Service Contract   - Image, port 8080, /healthz probe, sizing, SA
#   2. Instance Name Prefixing     - Resource naming & public module output contracts
#   3. Storage: Spanner Disabled   - try() fallbacks, zero Spanner IAM, no Vertex AI
#   4. Storage: Spanner Enabled    - Spanner reader IAM, Vertex AI role, env vars
#   5. Network: Private Ingress    - Omission of public allUsers invoker IAM binding
#   6. Network: Direct VPC Egress  - Subnetwork interface, tags, and egress mode
#   7. Secrets: Secret Manager     - Accessor IAM bindings & secret_key_ref injection
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
  image                         = "gcr.io/test/image:latest"
  cpu                           = "2"
  memory                        = "4Gi"
  min_instances                 = 0
  max_instances                 = 5
  make_public                   = true
  enable_mcp                    = false
  mcp_search_scope              = "custom_only"
  env_vars                      = []
  secret_env_vars               = []
  spanner_config                = null
  vpc_access                    = null
}

# =============================================================================
# SCENARIO 1: Baseline Service Contract
# =============================================================================
run "baseline_service_contract" {
  command = plan

  # 1. Container Image & Resource Limits
  assert {
    condition     = output.image == "gcr.io/test/image:latest"
    error_message = "output.image must reflect the configured container image URI"
  }

  assert {
    condition     = google_cloud_run_v2_service.dc_web_service.template[0].containers[0].resources[0].limits.cpu == "2" && google_cloud_run_v2_service.dc_web_service.template[0].containers[0].resources[0].limits.memory == "4Gi"
    error_message = "Cloud Run container CPU and Memory limits must match input variables"
  }

  # 2. Port & Health Check Probe
  assert {
    condition     = google_cloud_run_v2_service.dc_web_service.template[0].containers[0].ports[0].container_port == 8080
    error_message = "Serving container must expose port 8080"
  }

  assert {
    condition     = google_cloud_run_v2_service.dc_web_service.template[0].containers[0].startup_probe[0].http_get[0].path == "/healthz"
    error_message = "Startup probe must target the /healthz endpoint"
  }

  assert {
    condition     = google_cloud_run_v2_service.dc_web_service.template[0].containers[0].startup_probe[0].failure_threshold == 18
    error_message = "Startup probe failure threshold must be 18 (accommodating 3-minute deployment window)"
  }

  # 3. Service Account Identity & Default Ingress
  assert {
    condition     = google_service_account.serving_sa.account_id == "dc-srvs-sa"
    error_message = "Cloud Run service account ID must default to dc-srvs-sa"
  }

  assert {
    condition     = length(google_cloud_run_v2_service_iam_member.public_access) == 1
    error_message = "Default baseline with make_public = true must create the public invoker binding"
  }
}

# =============================================================================
# SCENARIO 2: Instance Name Prefixing & Public Output Contracts
# =============================================================================
run "instance_name_prefixing" {
  command = plan

  variables {
    instance_name = "prod"
  }

  assert {
    condition     = output.service_name == "prod-dc-datacommons-service"
    error_message = "output.service_name must be prefixed with the instance_name when provided"
  }

  assert {
    condition     = google_service_account.serving_sa.account_id == "prod-dc-srvs-sa"
    error_message = "Serving Service Account account_id must be prefixed with instance_name"
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
    condition     = length(google_spanner_database_iam_member.serving_spanner_reader) == 0
    error_message = "Database Reader IAM binding must NOT be created when spanner_config is null"
  }

  assert {
    condition     = !contains(keys(google_project_iam_member.serving_sa_roles), "roles/aiplatform.user")
    error_message = "roles/aiplatform.user must NOT be granted when spanner_config is null"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.value if e.name == "GCP_SPANNER_INSTANCE_ID"]) == ""
    error_message = "GCP_SPANNER_INSTANCE_ID must fall back to empty string via try() when spanner_config is null"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.value if e.name == "GCP_SPANNER_DATABASE_NAME"]) == ""
    error_message = "GCP_SPANNER_DATABASE_NAME must fall back to empty string via try() when spanner_config is null"
  }
}

# =============================================================================
# SCENARIO 4: Storage - Spanner Enabled (Reader IAM & Vertex AI role)
# =============================================================================
run "spanner_enabled_with_vertex_ai" {
  command = plan

  variables {
    spanner_config = {
      instance_id = "test-spanner-instance"
      database_id = "test-spanner-db"
    }
  }

  assert {
    condition     = length(google_spanner_database_iam_member.serving_spanner_reader) == 1
    error_message = "Database Reader IAM binding MUST be created when spanner_config is provided"
  }

  assert {
    condition     = google_spanner_database_iam_member.serving_spanner_reader[0].instance == "test-spanner-instance" && google_spanner_database_iam_member.serving_spanner_reader[0].database == "test-spanner-db"
    error_message = "Database Reader IAM binding must target configured instance and database"
  }

  assert {
    condition     = contains(keys(google_project_iam_member.serving_sa_roles), "roles/aiplatform.user")
    error_message = "roles/aiplatform.user MUST be granted when spanner_config is provided"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.value if e.name == "GCP_SPANNER_INSTANCE_ID"]) == "test-spanner-instance"
    error_message = "GCP_SPANNER_INSTANCE_ID must match spanner_config.instance_id"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.value if e.name == "GCP_SPANNER_DATABASE_NAME"]) == "test-spanner-db"
    error_message = "GCP_SPANNER_DATABASE_NAME must match spanner_config.database_id"
  }
}

# =============================================================================
# SCENARIO 5: Network Perimeter - Private Ingress
# =============================================================================
run "private_ingress" {
  command = plan

  variables {
    make_public = false
  }

  assert {
    condition     = length(google_cloud_run_v2_service_iam_member.public_access) == 0
    error_message = "Public invoker binding must NOT exist when make_public = false"
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
      vpc_egress_mode = "ALL_TRAFFIC"
    }
  }

  assert {
    condition     = length(google_cloud_run_v2_service.dc_web_service.template[0].vpc_access) == 1
    error_message = "vpc_access block must be generated when vpc_access is configured"
  }

  assert {
    condition     = google_cloud_run_v2_service.dc_web_service.template[0].vpc_access[0].egress == "ALL_TRAFFIC"
    error_message = "VPC egress mode must match configured vpc_egress_mode"
  }

  assert {
    condition     = google_cloud_run_v2_service.dc_web_service.template[0].vpc_access[0].network_interfaces[0].network == "projects/test-project/global/networks/test-vpc"
    error_message = "VPC network interface must match configured network_id"
  }
}

# =============================================================================
# SCENARIO 7: Secrets - Secret Manager Access & Env Injection
# =============================================================================
run "with_secrets_injection" {
  command = plan

  variables {
    secret_env_vars = [
      {
        name    = "CUSTOM_SECRET_KEY"
        secret  = "my-secret-id"
        version = "latest"
      }
    ]
  }

  assert {
    condition     = contains(keys(google_secret_manager_secret_iam_member.serving_secret_accessor), "CUSTOM_SECRET_KEY")
    error_message = "Secret accessor IAM binding must be created for configured secret"
  }

  assert {
    condition     = google_secret_manager_secret_iam_member.serving_secret_accessor["CUSTOM_SECRET_KEY"].secret_id == "my-secret-id"
    error_message = "Secret accessor IAM binding must target the exact secret_id"
  }

  assert {
    condition     = one([for e in google_cloud_run_v2_service.dc_web_service.template[0].containers[0].env : e.name if e.name == "CUSTOM_SECRET_KEY"]) == "CUSTOM_SECRET_KEY"
    error_message = "Container env list must include dynamic secret environment variable"
  }
}


