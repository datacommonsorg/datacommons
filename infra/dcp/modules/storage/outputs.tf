output "cdc_bucket_name" {
  value = var.enable_cdc ? google_storage_bucket.cdc_data_bucket[0].name : null
}

output "dcp_bucket_name" {
  value = var.enable_dcp && var.dcp_deploy ? (var.dcp_create_bucket ? google_storage_bucket.dcp_data_ingestion_bucket[0].name : var.dcp_external_bucket_name) : null
}

output "dcp_bucket_url" {
  value = var.enable_dcp && var.dcp_deploy ? (var.dcp_create_bucket ? google_storage_bucket.dcp_data_ingestion_bucket[0].url : null) : null
}
