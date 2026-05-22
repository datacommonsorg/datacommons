

output "spanner_instance_id" {
  value = module.spanner.spanner_instance_id
}

output "spanner_database_id" {
  value = module.spanner.spanner_database_id
}

output "datacommons_service_url" {
  value = length(module.datacommons_services) > 0 ? module.datacommons_services[0].service_url : null
}

output "datacommons_service_name" {
  value = length(module.datacommons_services) > 0 ? module.datacommons_services[0].service_name : null
}

output "ingestion_workflow_id" {
  description = "ID of the ingestion Cloud Workflows orchestrator"
  value       = module.ingestion_workflow.ingestion_orchestrator_id
}

output "ingestion_bucket_url" {
  description = "GCS URL pointing directly to the dynamically provisioned bucket for your input graph MCF files"
  value       = var.ingestion_config.enable_ingestion ? module.storage.ingestion_workflow_bucket_url : null
}

output "ingestion_workflow_name" {
  description = "Name of the ingestion Cloud Workflows orchestrator"
  value       = module.ingestion_workflow.ingestion_orchestrator_name
}

output "ingestion_service_uri" {
  description = "URI of the ingestion support Cloud Run service"
  value       = module.ingestion_helper_service.ingestion_helper_uri
}

output "ingestion_prep_job_name" {
  description = "Name of the data ingestion pre-processing job"
  value       = length(module.ingestion_preprocessing_job) > 0 ? module.ingestion_preprocessing_job[0].job_name : null
}

output "ingestion_orchestrator_service_account_email" {
  description = "Email of the orchestrator service account used by CLI and Workflows"
  value       = module.ingestion_dataflow.orchestrator_email
}

output "ingestion_input_bucket_name" {
  description = "Name of the GCS bucket used for data ingestion pre-processing"
  value       = module.storage.ingestion_input_bucket_name
}
