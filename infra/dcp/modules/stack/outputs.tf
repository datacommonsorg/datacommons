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

output "cdc_mysql_instance_connection_name" {
  value = var.toggles.enable_cdc && !var.toggles.enable_dcp ? module.cdc_mysql[0].mysql_instance_connection_name : null
}

output "dcp_ingestion_orchestrator_id" {
  description = "ID of the ingestion Cloud Workflows orchestrator"
  value       = var.toggles.enable_dcp && var.dcp.deploy_data_ingestion_workflow ? module.dcp_ingestion_workflow[0].ingestion_orchestrator_id : null
}

output "dcp_data_ingestion_bucket_url" {
  description = "GCS URL pointing directly to the dynamically provisioned bucket for your input graph MCF files"
  value       = var.toggles.enable_dcp && var.dcp.deploy_data_ingestion_workflow ? module.dcp_storage[0].bucket_url : null
}
