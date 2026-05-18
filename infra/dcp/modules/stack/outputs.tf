output "dcp_service_url" {
  value = var.toggles.enable_dcp ? module.dcp_service[0].service_url : null
}

output "dcp_spanner_instance_id" {
  value = var.toggles.enable_dcp ? module.spanner[0].spanner_instance_id : null
}

output "dcp_spanner_database_id" {
  value = var.toggles.enable_dcp ? module.spanner[0].spanner_database_id : null
}

output "cdc_service_url" {
  value = var.toggles.enable_cdc ? module.cdc_services[0].service_url : null
}

output "cdc_service_name" {
  value = var.toggles.enable_cdc ? module.cdc_services[0].service_name : null
}

output "cdc_mysql_instance_connection_name" {
  value = var.toggles.enable_cdc && !var.toggles.enable_dcp ? module.cdc_mysql[0].mysql_instance_connection_name : null
}

output "dcp_ingestion_orchestrator_id" {
  description = "ID of the ingestion Cloud Workflows orchestrator"
  value       = var.toggles.enable_dcp && var.dcp.deploy_data_ingestion_workflow ? module.dcp_ingestion_workflow[0].ingestion_orchestrator_id : null
}

output "dcp_data_ingestion_bucket_url" {
  description = "GCS URL pointing directly to the dynamically provisioned bucket for your input graph MCF files"
  value       = var.toggles.enable_dcp && var.dcp.deploy_data_ingestion_workflow ? module.storage.dcp_bucket_url : null
}

output "dcp_ingestion_orchestrator_name" {
  description = "Name of the ingestion Cloud Workflows orchestrator"
  value       = var.toggles.enable_dcp && var.dcp.deploy_data_ingestion_workflow ? module.dcp_ingestion_workflow[0].ingestion_orchestrator_name : null
}

output "dcp_ingestion_helper_uri" {
  description = "URI of the DCP ingestion helper Cloud Run service"
  value       = var.toggles.enable_dcp && var.dcp.deploy_data_ingestion_workflow ? module.dcp_ingestion_helper[0].ingestion_helper_uri : null
}

output "cdc_data_job_name" {
  description = "Name of the CDC Cloud Run data ingestion job"
  value       = var.toggles.enable_cdc ? module.cdc_data_ingestion_job[0].job_name : null
}

output "dcp_orchestrator_service_account_email" {
  description = "Email of the DCP orchestrator service account used by CLI and Workflows"
  value       = var.toggles.enable_dcp && var.dcp.deploy_data_ingestion_workflow ? module.dcp_ingestion_dataflow[0].orchestrator_email : null
}

output "data_bucket_name" {
  description = "Name of the GCS bucket used for CDC data ingestion"
  value       = var.toggles.enable_cdc ? module.storage.cdc_bucket_name : null
}



