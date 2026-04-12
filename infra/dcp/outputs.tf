# --- DCP Outputs ---
output "dcp_service_url" {
  value = var.enable_dcp ? module.dcp[0].service_url : null
}

output "dcp_spanner_instance_id" {
  value = var.enable_dcp ? module.dcp[0].spanner_instance_id : null
}

# --- CDC Outputs ---
output "cdc_service_url" {
  value = var.enable_cdc ? module.cdc[0].cloud_run_service_url : null
}

output "cdc_mysql_instance_connection_name" {
  value = var.enable_cdc ? module.cdc[0].mysql_instance_connection_name : null
}
