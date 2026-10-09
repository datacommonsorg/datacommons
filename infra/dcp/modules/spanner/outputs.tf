output "spanner_instance_id" {
  value = local.resolved_instance_id
}

output "spanner_database_id" {
  value = local.resolved_database_id
}

output "bigquery_connection_id" {
  value = var.enable_bigquery_connection ? google_bigquery_connection.spanner_connection[0].id : ""
}
