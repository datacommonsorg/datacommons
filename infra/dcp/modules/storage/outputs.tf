output "ingestion_input_bucket_name" {
  value = var.create_input_bucket ? google_storage_bucket.input_bucket[0].name : local.ingestion_input_bucket_name
}

output "ingestion_workflow_bucket_name" {
  value = var.deploy_workflow ? (var.create_workflow_bucket ? google_storage_bucket.workflow_bucket[0].name : local.ingestion_workflow_bucket_name) : null
}

output "ingestion_workflow_bucket_url" {
  value = var.deploy_workflow ? (var.create_workflow_bucket ? google_storage_bucket.workflow_bucket[0].url : "gs://${local.ingestion_workflow_bucket_name}") : null
}
