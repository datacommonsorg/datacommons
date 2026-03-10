output "service_url" {
  value = google_cloud_run_v2_service.dcp_service.uri
}

output "service_account_email" {
  value = google_service_account.dcp_runner.email
}

output "spanner_instance_id" {
  value = var.create_spanner ? google_spanner_instance.main[0].name : var.spanner_instance_id
}

output "spanner_database_id" {
  value = var.create_spanner ? google_spanner_database.database[0].name : var.spanner_database_id
}
