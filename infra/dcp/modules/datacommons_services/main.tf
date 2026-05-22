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
    "roles/cloudsql.admin",
    "roles/storage.objectAdmin",
    "roles/run.admin",
    "roles/vpcaccess.user",
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
  name                = "${local.name_prefix}dcp-datacommons-service"
  location            = var.region
  deletion_protection = var.deletion_protection

  template {
    timeout = "300s"
    containers {
      image = var.dc_web_service_image
      resources {
        limits = {
          cpu    = var.dc_web_service_cpu
          memory = var.dc_web_service_memory
        }
      }
      ports {
        container_port = 8080
      }

      startup_probe {
        timeout_seconds   = 120
        period_seconds    = 30
        failure_threshold = 6
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
        value = var.dc_search_scope
      }
      env {
        name  = "ENABLE_MCP"
        value = var.enable_mcp ? "true" : "false"
      }
      env {
        name  = "DC_INSTRUCTIONS_DIR"
        value = var.prep_bucket_name != "" ? "gs://${var.prep_bucket_name}/mcp_instructions" : ""
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
      min_instance_count = var.dc_web_service_min_instance_count
      max_instance_count = var.dc_web_service_max_instance_count
    }

    service_account = google_service_account.serving_sa.email

    dynamic "volumes" {
      for_each = var.use_spanner ? [] : [1]
      content {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [var.mysql_connection_name]
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count    = var.make_dc_web_service_public ? 1 : 0
  location = google_cloud_run_v2_service.dc_web_service.location
  project  = google_cloud_run_v2_service.dc_web_service.project
  name     = google_cloud_run_v2_service.dc_web_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
