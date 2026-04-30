locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
  display_name_prefix = var.namespace != "" ? "(${var.namespace}) " : ""
}

resource "google_service_account" "dcp_runner" {
  account_id   = "${local.name_prefix}${var.service_account_name}"
  display_name = "${local.display_name_prefix}Data Commons Platform Runner"
}

resource "google_project_iam_member" "spanner_user" {
  project = var.project_id
  role    = "roles/spanner.databaseUser"
  member  = "serviceAccount:${google_service_account.dcp_runner.email}"
}

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
        value = var.spanner_instance_id
      }
      env {
        name  = "GCP_SPANNER_DATABASE_NAME"
        value = var.spanner_database_id
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

resource "google_cloud_run_service_iam_binding" "public_invoker" {
  count    = var.make_service_public ? 1 : 0
  location = google_cloud_run_v2_service.dcp_service.location
  service  = google_cloud_run_v2_service.dcp_service.name
  role     = "roles/run.invoker"
  members  = ["allUsers"]
}
