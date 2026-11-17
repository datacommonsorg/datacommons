locals {
  name_prefix         = var.instance_name != "" ? "${var.instance_name}-" : ""
  display_name_prefix = var.instance_name != "" ? "(${var.instance_name}) " : ""
}

resource "google_service_account" "dataflow_sa" {
  count        = var.deploy ? 1 : 0
  account_id   = "${local.name_prefix}dc-ing-df-sa"
  display_name = "Data Commons Ingestion Dataflow SA"
}

resource "google_spanner_database_iam_member" "dataflow_spanner_user" {
  count    = var.deploy ? 1 : 0
  project  = var.project_id
  instance = var.spanner_config.instance_id
  database = var.spanner_config.database_id
  role     = "roles/spanner.databaseUser"
  member   = "serviceAccount:${google_service_account.dataflow_sa[0].email}"
}

resource "google_project_iam_member" "dataflow_worker" {
  count   = var.deploy ? 1 : 0
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.dataflow_sa[0].email}"
}
