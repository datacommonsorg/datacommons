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
