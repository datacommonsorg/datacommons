output "bucket_name" {
  value = var.deploy ? (var.create_bucket ? google_storage_bucket.data_ingestion_bucket[0].name : var.external_bucket_name) : null
}

output "bucket_url" {
  value = var.deploy ? (var.create_bucket ? google_storage_bucket.data_ingestion_bucket[0].url : null) : null
}
