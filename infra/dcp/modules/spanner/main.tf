locals {
  name_prefix           = var.namespace != "" ? "${var.namespace}-" : ""
  effective_instance_id = var.create_spanner_instance ? (var.spanner_instance_id != "" ? "${local.name_prefix}${var.spanner_instance_id}" : "${local.name_prefix}dcp-instance") : var.spanner_instance_id
  effective_database_id = var.create_spanner_db ? (var.spanner_database_id != "" ? "${local.name_prefix}${var.spanner_database_id}" : "${local.name_prefix}dcp-db") : var.spanner_database_id
}

resource "google_spanner_instance" "main" {
  count            = var.create_spanner_instance ? 1 : 0
  name             = local.effective_instance_id
  config           = "regional-${var.region}"
  display_name     = local.effective_instance_id
  processing_units = var.spanner_processing_units
  force_destroy    = !var.deletion_protection
  edition          = "ENTERPRISE"
}

resource "google_spanner_database" "database" {
  count    = var.create_spanner_db ? 1 : 0
  instance = var.create_spanner_instance ? google_spanner_instance.main[0].name : local.effective_instance_id
  name     = local.effective_database_id

  deletion_protection = var.deletion_protection
}

resource "google_spanner_database_iam_member" "orchestrator_spanner_user" {
  count    = var.create_spanner_db && var.orchestrator_email != "" ? 1 : 0
  instance = var.create_spanner_instance ? google_spanner_instance.main[0].name : local.effective_instance_id
  database = google_spanner_database.database[0].name
  role     = "roles/spanner.databaseUser"
  member   = "serviceAccount:${var.orchestrator_email}"
}

data "google_project" "current" {}

# Create BigQuery Connection to Spanner
resource "google_bigquery_connection" "spanner_connection" {
  count         = var.create_spanner_db && var.enable_bq_federation ? 1 : 0
  location      = var.region
  connection_id = "${local.name_prefix}${var.bq_connection_name}"
  description   = "Federated connection to Spanner for custom DC"

  cloud_spanner {
    database = "projects/${data.google_project.current.project_id}/instances/${var.create_spanner_instance ? google_spanner_instance.main[0].name : local.effective_instance_id}/databases/${google_spanner_database.database[0].name}"
    use_parallelism = true
  }
}

# Grant the connection's service account access to Spanner
resource "google_spanner_database_iam_member" "spanner_reader" {
  count    = var.create_spanner_db && var.enable_bq_federation ? 1 : 0
  instance = var.create_spanner_instance ? google_spanner_instance.main[0].name : local.effective_instance_id
  database = google_spanner_database.database[0].name
  role     = "roles/spanner.databaseUser"
  member   = "serviceAccount:${google_bigquery_connection.spanner_connection[0].cloud_spanner[0].service_account_id}"
}

# Grant Ingestion Helper access to use the connection
resource "google_project_iam_member" "helper_connection_user" {
  count   = var.create_spanner_db && var.enable_bq_federation && var.ingestion_helper_sa_email != "" ? 1 : 0
  project = data.google_project.current.project_id
  role    = "roles/bigquery.connectionUser"
  member  = "serviceAccount:${var.ingestion_helper_sa_email}"
}

# Grant Ingestion Helper access to create/edit tables in BigQuery
resource "google_project_iam_member" "helper_bq_editor" {
  count   = var.create_spanner_db && var.enable_bq_federation && var.ingestion_helper_sa_email != "" ? 1 : 0
  project = data.google_project.current.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${var.ingestion_helper_sa_email}"
}
