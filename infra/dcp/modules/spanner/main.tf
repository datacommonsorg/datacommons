locals {
  name_prefix           = var.namespace != "" ? "${var.namespace}-" : ""
  effective_instance_id = var.create_instance ? (var.instance_id != "" ? "${local.name_prefix}${var.instance_id}" : "${local.name_prefix}dc-instance") : var.instance_id
  effective_database_id = var.create_database ? (var.database_id != "" ? "${local.name_prefix}${var.database_id}" : "${local.name_prefix}dc-db") : var.database_id
}

resource "google_spanner_instance" "main" {
  count            = var.create_instance ? 1 : 0
  name             = local.effective_instance_id
  config           = "regional-${var.region}"
  display_name     = local.effective_instance_id
  processing_units = var.processing_units
  force_destroy    = !var.deletion_protection
  edition          = "ENTERPRISE"
}

resource "google_spanner_database" "database" {
  count    = var.create_database ? 1 : 0
  instance = var.create_instance ? google_spanner_instance.main[0].name : local.effective_instance_id
  name     = local.effective_database_id

  deletion_protection      = var.deletion_protection
  version_retention_period = var.version_retention_period
}



data "google_bigquery_default_service_account" "bq_sa" {
  project = var.project_id
}

# Create BigQuery Connection to Spanner
resource "google_bigquery_connection" "spanner_connection" {
  count         = var.enable_bigquery_connection ? 1 : 0
  location      = var.region
  connection_id = replace("${local.name_prefix}dc_${var.bigquery_connection_name}", "-", "_")
  description   = "Federated connection to Spanner for custom DC"

  cloud_spanner {
    database = "projects/${var.project_id}/instances/${var.create_instance ? google_spanner_instance.main[0].name : local.effective_instance_id}/databases/${var.create_database ? google_spanner_database.database[0].name : local.effective_database_id}"
    use_parallelism = true
  }
}

# Grant the connection's service account access to Spanner
resource "google_spanner_database_iam_member" "spanner_reader" {
  count    = var.enable_bigquery_connection ? 1 : 0
  instance = var.create_instance ? google_spanner_instance.main[0].name : local.effective_instance_id
  database = var.create_database ? google_spanner_database.database[0].name : local.effective_database_id
  role     = "roles/spanner.databaseUser"
  member   = "serviceAccount:${data.google_bigquery_default_service_account.bq_sa.email}"
}


# Create the BigQuery Reservation for Federation queries
resource "google_bigquery_reservation" "default" {
  count         = var.enable_bigquery_connection && var.create_bigquery_reservation ? 1 : 0
  name          = "default"
  location      = var.region
  edition       = "ENTERPRISE"
  slot_capacity = var.bigquery_reservation_slot_capacity

  autoscale {
    max_slots = var.bigquery_reservation_max_slots
  }
}

# Assign the reservation to the project for queries
resource "google_bigquery_reservation_assignment" "project_assignment" {
  count       = var.enable_bigquery_connection && var.create_bigquery_reservation ? 1 : 0
  reservation = google_bigquery_reservation.default[0].id
  assignee    = "projects/${var.project_id}"
  job_type    = "QUERY"
}
