locals {
  name_prefix         = var.namespace != "" ? "${var.namespace}-" : ""
  display_name_prefix = var.namespace != "" ? "(${var.namespace}) " : ""
}

resource "google_service_account" "dataflow_sa" {
  count        = var.deploy ? 1 : 0
  account_id   = "${local.name_prefix}dc-ing-df-sa"
  display_name = "Data Commons Ingestion Dataflow SA"
}

resource "google_project_iam_member" "ingestion_spanner_user" {
  count   = var.deploy && var.use_spanner ? 1 : 0
  project = var.project_id
  role    = "roles/spanner.databaseUser"
  member  = "serviceAccount:${google_service_account.dataflow_sa[0].email}"
}



resource "google_project_iam_member" "dataflow_worker" {
  count   = var.deploy ? 1 : 0
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.dataflow_sa[0].email}"
}

# This is only needed to trigger the services restart to pick up the GCS embeddings change

resource "google_service_account_iam_member" "service_account_user" {
  count              = var.deploy ? 1 : 0
  service_account_id = google_service_account.dataflow_sa[0].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.dataflow_sa[0].email}"
}

data "google_project" "project" {
  project_id = var.project_id
}

resource "google_service_account_iam_member" "workflows_token_creator" {
  count              = var.deploy ? 1 : 0
  service_account_id = google_service_account.dataflow_sa[0].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-workflows.iam.gserviceaccount.com"
}


