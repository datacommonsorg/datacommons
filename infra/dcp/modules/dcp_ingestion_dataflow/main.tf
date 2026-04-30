locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
  display_name_prefix = var.namespace != "" ? "(${var.namespace}) " : ""
}

resource "google_service_account" "dcp_ingestion_runner" {
  count        = var.deploy ? 1 : 0
  account_id   = "${local.name_prefix}dcp-ingestion-sa"
  display_name = "${local.display_name_prefix}Data Commons Platform Ingestion Runner"
}

resource "google_project_iam_member" "ingestion_spanner_user" {
  count   = var.deploy ? 1 : 0
  project = var.project_id
  role    = "roles/spanner.databaseUser"
  member  = "serviceAccount:${google_service_account.dcp_ingestion_runner[0].email}"
}

resource "google_project_iam_member" "dataflow_admin" {
  count   = var.deploy ? 1 : 0
  project = var.project_id
  role    = "roles/dataflow.admin"
  member  = "serviceAccount:${google_service_account.dcp_ingestion_runner[0].email}"
}

resource "google_project_iam_member" "dataflow_worker" {
  count   = var.deploy ? 1 : 0
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.dcp_ingestion_runner[0].email}"
}

resource "google_service_account_iam_member" "service_account_user" {
  count              = var.deploy ? 1 : 0
  service_account_id = google_service_account.dcp_ingestion_runner[0].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.dcp_ingestion_runner[0].email}"
}

data "google_project" "project" {
  project_id = var.project_id
}

resource "google_service_account_iam_member" "workflows_token_creator" {
  count              = var.deploy ? 1 : 0
  service_account_id = google_service_account.dcp_ingestion_runner[0].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-workflows.iam.gserviceaccount.com"
}

resource "google_storage_bucket_iam_member" "dynamic_ingestion_bucket_access" {
  count  = var.deploy ? 1 : 0
  bucket = var.ingestion_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dcp_ingestion_runner[0].email}"
}
