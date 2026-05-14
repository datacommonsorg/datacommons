output "dcp_service_url" {
  value = module.stack.dcp_service_url
}

output "dcp_spanner_instance_id" {
  value = module.stack.dcp_spanner_instance_id
}

output "dcp_spanner_database_id" {
  value = module.stack.dcp_spanner_database_id
}

output "cdc_service_url" {
  value = module.stack.cdc_service_url
}

output "cdc_mysql_instance_connection_name" {
  value = module.stack.cdc_mysql_instance_connection_name
}

output "dcp_ingestion_orchestrator_id" {
  description = "ID of the ingestion Cloud Workflows orchestrator"
  value       = module.stack.dcp_ingestion_orchestrator_id
}

output "dcp_data_ingestion_bucket_url" {
  description = "GCS URL pointing directly to the dynamically provisioned bucket for your input graph MCF files"
  value       = module.stack.dcp_data_ingestion_bucket_url
}

output "workflow_name" {
  description = "Name of the ingestion Cloud Workflows orchestrator"
  value       = module.stack.dcp_ingestion_orchestrator_name
}

output "dcp_ingestion_helper_uri" {
  description = "URI of the DCP ingestion helper Cloud Run service"
  value       = module.stack.dcp_ingestion_helper_uri
}

output "cdc_data_job_name" {
  description = "Name of the CDC Cloud Run data ingestion job"
  value       = module.stack.cdc_data_job_name
}

output "dcp_orchestrator_service_account_email" {
  description = "Email of the DCP orchestrator service account used by CLI and Workflows"
  value       = module.stack.dcp_orchestrator_service_account_email
}

