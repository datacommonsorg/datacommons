
output "spanner_instance_id" {
  value = module.stack.spanner_instance_id
}

output "spanner_database_id" {
  value = module.stack.spanner_database_id
}

output "datacommons_service_url" {
  value = module.stack.datacommons_service_url
}

output "datacommons_service_name" {
  value = module.stack.datacommons_service_name
}

output "ingestion_workflow_id" {
  description = "ID of the ingestion Cloud Workflows orchestrator"
  value       = module.stack.ingestion_workflow_id
}

output "ingestion_bucket_url" {
  description = "GCS URL pointing directly to the dynamically provisioned bucket for your input graph MCF files"
  value       = module.stack.ingestion_bucket_url
}

output "ingestion_workflow_name" {
  description = "Name of the ingestion Cloud Workflows orchestrator"
  value       = module.stack.ingestion_workflow_name
}

output "ingestion_service_url" {
  description = "URL of the ingestion support Cloud Run service"
  value       = module.stack.ingestion_service_url
}

output "ingestion_prep_job_name" {
  description = "Name of the data ingestion pre-processing job"
  value       = module.stack.ingestion_prep_job_name
}

output "ingestion_workflow_service_account_email" {
  description = "Email of the service account used by the ingestion workflow"
  value       = module.stack.ingestion_workflow_service_account_email
}

output "storage_artifacts_bucket_name" {
  description = "Name of the unified GCS bucket for artifacts"
  value       = module.stack.storage_artifacts_bucket_name
}

output "project_id" {
  description = "The GCP project ID where resources are deployed"
  value       = var.project_id
}

output "region" {
  description = "The GCP region where resources are deployed"
  value       = var.region
}

output "ingestion_input_path" {
  description = "The GCS root directory where input data files are stored."
  value       = var.ingestion_input_path
}