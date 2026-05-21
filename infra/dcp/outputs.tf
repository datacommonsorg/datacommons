output "platform_service_url" {
  value = module.stack.platform_service_url
}

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

output "ingestion_service_uri" {
  description = "URI of the ingestion support Cloud Run service"
  value       = module.stack.ingestion_service_uri
}

output "ingestion_prep_job_name" {
  description = "Name of the data ingestion pre-processing job"
  value       = module.stack.ingestion_prep_job_name
}

output "ingestion_orchestrator_service_account_email" {
  description = "Email of the orchestrator service account used by CLI and Workflows"
  value       = module.stack.ingestion_orchestrator_service_account_email
}

output "ingestion_input_bucket_name" {
  description = "Name of the GCS bucket used for data ingestion pre-processing"
  value       = module.stack.ingestion_input_bucket_name
}

output "project_id" {
  description = "The GCP project ID where resources are deployed"
  value       = var.project_id
}

output "region" {
  description = "The GCP region where resources are deployed"
  value       = var.region
}
