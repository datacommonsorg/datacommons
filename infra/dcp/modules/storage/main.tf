locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
  cdc_gcs_data_bucket_name = var.cdc_gcs_data_bucket_name != "" ? var.cdc_gcs_data_bucket_name : "${local.name_prefix}datacommons-data-${var.project_id}"
}

resource "google_storage_bucket" "cdc_data_bucket" {
  count                       = var.enable_cdc ? 1 : 0
  name                        = local.cdc_gcs_data_bucket_name
  location                    = var.cdc_gcs_data_bucket_location
  force_destroy               = true
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "dcp_data_ingestion_bucket" {
  count                       = var.enable_dcp && var.dcp_deploy && var.dcp_create_bucket ? 1 : 0
  name                        = "${local.name_prefix}ingestion-bucket-${var.project_id}"
  location                    = var.dcp_region
  uniform_bucket_level_access = true
  force_destroy               = !var.dcp_deletion_protection
}

resource "google_storage_bucket_iam_member" "orchestrator_cdc_bucket" {
  count  = var.enable_cdc && var.orchestrator_email != "" ? 1 : 0
  bucket = google_storage_bucket.cdc_data_bucket[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.orchestrator_email}"
}

resource "google_storage_bucket_iam_member" "orchestrator_dcp_bucket" {
  count  = var.enable_dcp && var.dcp_deploy && var.dcp_create_bucket && var.orchestrator_email != "" ? 1 : 0
  bucket = google_storage_bucket.dcp_data_ingestion_bucket[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.orchestrator_email}"
}
