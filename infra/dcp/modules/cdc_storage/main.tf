locals {
  name_prefix          = var.namespace != "" ? "${var.namespace}-" : ""
  gcs_data_bucket_name = var.gcs_data_bucket_name != "" ? var.gcs_data_bucket_name : "${local.name_prefix}datacommons-data-${var.project_id}"
}

resource "google_storage_bucket" "data_bucket" {
  name          = local.gcs_data_bucket_name
  location      = var.gcs_data_bucket_location
  force_destroy = true

  uniform_bucket_level_access = true
}
