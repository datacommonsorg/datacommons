resource "google_cloud_run_v2_service" "ingestion_helper" {
  count    = var.deploy_data_ingestion_workflow ? 1 : 0
  name     = "${var.namespace}-ingestion-helper"
  location = var.region
  
  deletion_protection = var.deletion_protection

  template {
    containers {
      # TODO(gmechali): Change this to a stable image.
      image = "gcr.io/datcom-ci/datacommons-ingestion-helper:latest"
      
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      # TODO(gmechali): Remove this once we no longer use the :latest image.
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
        value = var.create_spanner_db ? (var.spanner_database_id != "" ? "${local.name_prefix}${var.spanner_database_id}" : "${local.name_prefix}dcp-db") : var.spanner_database_id
      }
      env {
        name  = "LOCATION"
        value = var.region
      }
      env {
        name  = "GCS_BUCKET_ID"
        value = var.create_ingestion_bucket ? google_storage_bucket.data_ingestion_bucket[0].name : var.external_ingestion_bucket_name
      }
    }
    service_account = google_service_account.dcp_ingestion_runner[0].email
  }
}
