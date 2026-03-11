resource "google_cloud_run_v2_service" "dcp_service" {
  name                = "${local.name_prefix}${var.service_name}"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.deletion_protection

  template {
    service_account                  = google_service_account.dcp_runner.email
    timeout                          = "${var.service_timeout_seconds}s"
    max_instance_request_concurrency = var.service_concurrency

    scaling {
      min_instance_count = var.service_min_instances
      max_instance_count = var.service_max_instances
    }

    containers {
      image = var.image_url

      resources {
        limits = {
          cpu    = var.service_cpu
          memory = var.service_memory
        }
      }

      ports {
        container_port = 5000
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_SPANNER_INSTANCE_ID"
        value = var.create_spanner_instance ? (var.spanner_instance_id != "" ? "${local.name_prefix}${var.spanner_instance_id}" : "${local.name_prefix}dcp-instance") : var.spanner_instance_id
      }
      env {
        name  = "GCP_SPANNER_DATABASE_NAME"
        value = var.create_spanner_db ? (var.spanner_database_id != "" ? "${local.name_prefix}${var.spanner_database_id}" : "${local.name_prefix}dcp-db") : var.spanner_database_id
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

}
