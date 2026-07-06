locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
}

resource "google_service_account" "serving_sa" {
  account_id   = "${local.name_prefix}dc-srvs-sa"
  display_name = "Data Commons Serving Service Account"
}

resource "google_project_iam_member" "serving_sa_roles" {
  for_each = setsubtract(toset([
    "roles/compute.networkViewer",
    "roles/redis.editor",
    "roles/storage.objectViewer",
    "roles/vpcaccess.user",
    # TODO: Review this overly broad permission.
    "roles/iam.serviceAccountUser",
    "roles/secretmanager.secretAccessor",
    "roles/spanner.databaseUser",
    "roles/workflows.invoker"
  ]), var.use_spanner ? [] : ["roles/spanner.databaseUser"])

  project = var.project_id
  member  = "serviceAccount:${google_service_account.serving_sa.email}"
  role    = each.value
}

resource "google_cloud_run_v2_service" "dc_web_service" {
  name                = "${local.name_prefix}dc-datacommons-service"
  location            = var.region
  deletion_protection = var.stateless_deletion_protection

  template {
    timeout = "300s"
    containers {
      image = var.image
      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
      }
      ports {
        container_port = 8080
      }

      startup_probe {
        timeout_seconds   = 29
        period_seconds    = 30
        failure_threshold = 6 # 15 minutes of waiting
        tcp_socket {
          port = 8080
        }
      }

      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.value.name
          value = env.value.value
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name = env.value.name
          value_source {
            secret_key_ref {
              secret  = env.value.secret
              version = env.value.version
            }
          }
        }
      }

      env {
        name  = "GOOGLE_ANALYTICS_TAG_ID"
        value = var.google_analytics_tag_id != null ? var.google_analytics_tag_id : ""
      }
      env {
        name  = "DC_SEARCH_SCOPE"
        value = var.mcp_search_scope
      }
      env {
        name  = "ENABLE_MCP"
        value = var.enable_mcp ? "true" : "false"
      }
      env {
        name  = "DC_INSTRUCTIONS_DIR"
        value = var.mcp_instructions_path != null ? "gs://${var.artifacts_bucket_name}/${var.mcp_instructions_path}" : ""
      }
      env {
        name  = "RESOLVE_WITH_SPANNER_EMBEDDINGS"
        value = var.resolve_with_spanner_embeddings ? "true" : "false"
      }
      env {
        name  = "ENABLE_UNIQUE_HISTORY_RECORDS"
        value = var.enable_unique_history_records ? "true" : "false"
      }
    }

    dynamic "vpc_access" {
      for_each = var.vpc_connector_id != null && var.vpc_connector_id != "" ? [1] : []
      content {
        connector = var.vpc_connector_id
        egress    = "PRIVATE_RANGES_ONLY"
      }
    }


    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    service_account = google_service_account.serving_sa.email

  }

  depends_on = [google_project_iam_member.serving_sa_roles]
}

resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count    = var.make_public ? 1 : 0
  location = google_cloud_run_v2_service.dc_web_service.location
  project  = google_cloud_run_v2_service.dc_web_service.project
  name     = google_cloud_run_v2_service.dc_web_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
