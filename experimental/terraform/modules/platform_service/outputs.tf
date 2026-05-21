output "service_url" {
  value = google_cloud_run_v2_service.service.uri
}

output "service_account_email" {
  value = google_service_account.runner.email
}
