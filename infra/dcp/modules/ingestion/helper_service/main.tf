locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
}

resource "google_service_account" "helper_sa" {
  count        = var.deploy ? 1 : 0
  account_id   = "${local.name_prefix}dc-ing-hlp-sa"
  display_name = "Data Commons Ingestion Helper SA"
}

resource "google_cloud_run_v2_service" "ingestion_helper" {
  count               = var.deploy ? 1 : 0
  name                = "${local.name_prefix}dc-ingestion-helper"
  location            = var.region
  deletion_protection = var.deletion_protection

  template {
    containers {
      image = var.image

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
        name  = "SPANNER_GRAPH_DATABASE_ID"
        value = var.spanner_database_id
      }
      env {
        name  = "BQ_SPANNER_CONN_ID"
        value = var.bigquery_connection_id
      }
      env {
        name  = "BQ_JOB_SERVICE_ACCOUNT"
        value = var.bigquery_job_service_account
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

    service_account = google_service_account.helper_sa[0].email
  }
}

resource "google_project_iam_member" "helper_spanner_user" {
  count   = var.deploy && var.use_spanner ? 1 : 0
  project = var.project_id
  role    = "roles/spanner.databaseUser"
  member  = "serviceAccount:${google_service_account.helper_sa[0].email}"
}


resource "google_storage_bucket_iam_member" "helper_bucket_access" {
  count  = var.deploy ? 1 : 0
  bucket = var.ingestion_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.helper_sa[0].email}"
}

resource "google_project_iam_member" "helper_bq_editor" {
  count   = var.deploy ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.helper_sa[0].email}"
}

resource "google_project_iam_member" "helper_bq_job_user" {
  count   = var.deploy ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.helper_sa[0].email}"
}

resource "google_bigquery_connection_iam_member" "helper_connection_user" {
  count         = var.deploy && var.bigquery_connection_id != "" ? 1 : 0
  project       = var.project_id
  location      = var.region
  connection_id = var.bigquery_connection_id
  role          = "roles/bigquery.connectionUser"
  member        = "serviceAccount:${google_service_account.helper_sa[0].email}"
}




