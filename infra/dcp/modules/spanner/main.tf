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
