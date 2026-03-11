resource "google_spanner_instance" "main" {
  count            = var.create_spanner_instance ? 1 : 0
  name             = (var.create_spanner_instance && var.spanner_instance_id != "") ? "${local.name_prefix}${var.spanner_instance_id}" : "unused-instance"
  config           = "regional-${var.region}"
  display_name     = "${local.name_prefix}${var.spanner_instance_id}"
  processing_units = var.spanner_processing_units
  force_destroy    = !var.deletion_protection

}

resource "google_spanner_database" "database" {
  count    = var.create_spanner_db ? 1 : 0
  instance = var.create_spanner_instance ? google_spanner_instance.main[0].name : (var.spanner_instance_id != "" ? "${local.name_prefix}${var.spanner_instance_id}" : "unused-instance")
  name     = "${local.name_prefix}${var.spanner_database_id}"

  # Prevent deletion of data
  deletion_protection = var.deletion_protection
}
