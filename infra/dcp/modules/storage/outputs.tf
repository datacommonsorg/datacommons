output "ingestion_input_bucket_name" {
  value = var.enable_datacommons_service ? (var.create_prep_bucket ? google_storage_bucket.prep_bucket[0].name : local.ingestion_input_bucket_name) : null
}

output "ingestion_workflow_bucket_name" {
  value = var.enable_platform_service && var.deploy_pipeline ? (var.create_pipeline_bucket ? google_storage_bucket.pipeline_bucket[0].name : local.ingestion_workflow_bucket_name) : null
}

output "pipeline_bucket_url" {
  value = var.enable_platform_service && var.deploy_pipeline ? (var.create_pipeline_bucket ? google_storage_bucket.pipeline_bucket[0].url : null) : null
}
