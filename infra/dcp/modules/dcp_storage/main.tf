locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
}

resource "google_storage_bucket" "data_ingestion_bucket" {
  count                       = var.deploy && var.create_bucket ? 1 : 0
  name                        = "${local.name_prefix}ingestion-bucket-${var.project_id}"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = !var.deletion_protection
}
