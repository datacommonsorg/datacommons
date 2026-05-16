output "service_url" {
  value = google_cloud_run_v2_service.dcp_service.uri
}

output "service_account_email" {
  value = google_service_account.dcp_runner.email
}
