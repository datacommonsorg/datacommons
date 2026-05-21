locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
  ingestion_input_bucket_name = var.ingestion_input_bucket_name != "" ? var.ingestion_input_bucket_name : "${local.name_prefix}ingestion-input-${var.project_id}"
  ingestion_workflow_bucket_name = var.ingestion_workflow_bucket_name != "" ? var.ingestion_workflow_bucket_name : "${local.name_prefix}ingestion-workflow-${var.project_id}"
}

resource "google_storage_bucket" "prep_bucket" {
  count                       = var.enable_datacommons_service && var.create_prep_bucket ? 1 : 0
  name                        = local.ingestion_input_bucket_name
  location                    = var.prep_bucket_location
  force_destroy               = true
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "pipeline_bucket" {
  count                       = var.enable_platform_service && var.deploy_pipeline && var.create_pipeline_bucket ? 1 : 0
  name                        = local.ingestion_workflow_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = !var.deletion_protection
}

resource "google_storage_bucket_iam_member" "orchestrator_prep_bucket" {
  count  = var.enable_datacommons_service && var.orchestrator_email != "" ? 1 : 0
  bucket = var.create_prep_bucket ? google_storage_bucket.prep_bucket[0].name : local.ingestion_input_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.orchestrator_email}"
}

resource "google_storage_bucket_iam_member" "orchestrator_pipeline_bucket" {
  count  = var.enable_platform_service && var.deploy_pipeline && var.orchestrator_email != "" ? 1 : 0
  bucket = var.create_pipeline_bucket ? google_storage_bucket.pipeline_bucket[0].name : local.ingestion_workflow_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.orchestrator_email}"
}
