output "service_url" {
  value = google_cloud_run_v2_service.dcp_service.uri
}

output "service_account_email" {
  value = google_service_account.dcp_runner.email
}

output "spanner_instance_id" {
  value = var.create_spanner_instance ? (var.spanner_instance_id != "" ? "${local.name_prefix}${var.spanner_instance_id}" : "${local.name_prefix}dcp-instance") : var.spanner_instance_id
}

output "spanner_database_id" {
  value = var.create_spanner_db ? (var.spanner_database_id != "" ? "${local.name_prefix}${var.spanner_database_id}" : "${local.name_prefix}dcp-db") : var.spanner_database_id
}

output "ingestion_orchestrator_id" {
  description = "Fully qualified ID of the Cloud Workflows ingestion orchestrator"
  value       = var.deploy_data_ingestion_workflow ? google_workflows_workflow.ingestion_orchestrator[0].id : null
}
output "data_ingestion_bucket_url" {
  description = "GCS path to the dynamically provisioned staging bucket for customer custom MCF datasets"
  value       = var.deploy_data_ingestion_workflow && var.create_ingestion_bucket ? google_storage_bucket.data_ingestion_bucket[0].url : null
}
