output "spanner_instance_id" {
  value = local.effective_instance_id
}

output "spanner_database_id" {
  value = local.effective_database_id
}

output "bq_connection_id" {
  value = var.create_spanner_db && var.enable_bq_federation ? google_bigquery_connection.spanner_connection[0].id : ""
}
