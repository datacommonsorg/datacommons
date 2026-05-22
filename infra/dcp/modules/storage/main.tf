locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
  ingestion_input_bucket_name = var.ingestion_input_bucket_name != "" ? var.ingestion_input_bucket_name : "${local.name_prefix}ingestion-input-${var.project_id}"
  ingestion_workflow_bucket_name = var.ingestion_workflow_bucket_name != "" ? var.ingestion_workflow_bucket_name : "${local.name_prefix}ingestion-workflow-${var.project_id}"
}

resource "google_storage_bucket" "input_bucket" {
  count                       = var.create_input_bucket ? 1 : 0
  name                        = local.ingestion_input_bucket_name
  location                    = var.input_bucket_location
  force_destroy               = true
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "workflow_bucket" {
  count                       = var.deploy_workflow && var.create_workflow_bucket ? 1 : 0
  name                        = local.ingestion_workflow_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = !var.deletion_protection
}

