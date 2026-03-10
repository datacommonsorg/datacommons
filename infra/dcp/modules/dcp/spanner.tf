resource "google_spanner_instance" "main" {
  count            = var.create_spanner ? 1 : 0
  name             = var.spanner_instance_id
  config           = "regional-${var.region}"
  display_name     = var.spanner_instance_id
  processing_units = var.spanner_processing_units
  force_destroy    = !var.deletion_protection

}

resource "google_spanner_database" "database" {
  count    = var.create_spanner ? 1 : 0
  instance = google_spanner_instance.main[0].name
  name     = var.spanner_database_id

  # Prevent deletion of data
  deletion_protection = var.deletion_protection
}
