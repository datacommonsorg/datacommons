

output "spanner_instance_id" {
  value = var.spanner_config.enable ? module.spanner[0].spanner_instance_id : null
}

output "spanner_database_id" {
  value = var.spanner_config.enable ? module.spanner[0].spanner_database_id : null
}

output "datacommons_service_url" {
  value = length(module.datacommons_services) > 0 ? module.datacommons_services[0].service_url : null
}

output "datacommons_service_name" {
  value = length(module.datacommons_services) > 0 ? module.datacommons_services[0].service_name : null
}

output "ingestion_workflow_id" {
  description = "ID of the ingestion Cloud Workflow"
  value       = module.ingestion_workflow.workflow_id
}

output "ingestion_bucket_url" {
  description = "GCS URL pointing directly to the dynamically provisioned bucket for your input graph MCF files"
  value       = var.ingestion_config.enable_ingestion ? module.storage.artifacts_bucket_url : null
}

output "ingestion_workflow_name" {
  description = "Name of the ingestion Cloud Workflow"
  value       = module.ingestion_workflow.workflow_name
}

output "ingestion_service_url" {
  description = "URL of the ingestion support Cloud Run service"
  value       = module.ingestion_helper_service.ingestion_helper_url
}

output "ingestion_prep_job_name" {
  description = "Name of the data ingestion pre-processing job"
  value       = length(module.ingestion_preprocessing_job) > 0 ? module.ingestion_preprocessing_job[0].job_name : null
}

output "ingestion_workflow_service_account_email" {
  description = "Email of the service account used by the ingestion workflow"
  value       = module.ingestion_workflow.service_account_email
}

output "storage_artifacts_bucket_name" {
  description = "Name of the unified GCS bucket for artifacts"
  value       = module.storage.artifacts_bucket_name
}
