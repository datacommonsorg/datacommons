output "prep_bucket_name" {
  value = var.enable_cdc ? (var.create_prep_bucket ? google_storage_bucket.prep_bucket[0].name : local.prep_bucket_name) : null
}

output "pipeline_bucket_name" {
  value = var.enable_dcp && var.deploy_pipeline ? (var.create_pipeline_bucket ? google_storage_bucket.pipeline_bucket[0].name : local.pipeline_bucket_name) : null
}

output "pipeline_bucket_url" {
  value = var.enable_dcp && var.deploy_pipeline ? (var.create_pipeline_bucket ? google_storage_bucket.pipeline_bucket[0].url : null) : null
}
