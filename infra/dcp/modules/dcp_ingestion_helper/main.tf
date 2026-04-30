locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
}

resource "google_cloud_run_v2_service" "ingestion_helper" {
  count               = var.deploy ? 1 : 0
  name                = "${local.name_prefix}ingestion-helper"
  location            = var.region
  deletion_protection = var.deletion_protection

  template {
    containers {
      image = "gcr.io/datcom-ci/datacommons-ingestion-helper:latest"

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "FORCE_RESTART"
        value = timestamp()
      }
      env {
        name  = "SPANNER_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "SPANNER_INSTANCE_ID"
        value = var.spanner_instance_id
      }
      env {
        name  = "SPANNER_DATABASE_ID"
        value = var.spanner_database_id
      }
      env {
        name  = "LOCATION"
        value = var.region
      }
      env {
        name  = "GCS_BUCKET_ID"
        value = var.ingestion_bucket_name
      }
    }

    service_account = var.service_account_email
  }
}

resource "google_cloud_run_v2_service_iam_member" "ingestion_helper_invoker" {
  count    = var.deploy ? 1 : 0
  location = google_cloud_run_v2_service.ingestion_helper[0].location
  name     = google_cloud_run_v2_service.ingestion_helper[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.service_account_email}"
}
