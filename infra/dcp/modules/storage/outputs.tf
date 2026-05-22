output "artifacts_bucket_name" {
  value = var.create_artifacts_bucket ? google_storage_bucket.artifacts_bucket[0].name : local.artifacts_bucket_name
}

output "artifacts_bucket_url" {
  value = var.create_artifacts_bucket ? google_storage_bucket.artifacts_bucket[0].url : "gs://${local.artifacts_bucket_name}"
}
