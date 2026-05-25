output "spanner_instance_id" {
  value = local.effective_instance_id
}

output "spanner_database_id" {
  value = local.effective_database_id
}

output "bigquery_connection_id" {
  value = var.enable_bigquery_connection ? "projects/${var.project_id}/locations/${var.region}/connections/${replace("${local.name_prefix}dc_${var.bigquery_connection_name}", "-", "_")}" : ""
}
