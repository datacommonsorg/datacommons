output "service_name" {
  value = google_cloud_run_v2_service.dc_web_service.name
}

output "service_url" {
  value = google_cloud_run_v2_service.dc_web_service.uri
}

output "service_account_email" {
  value = google_service_account.serving_sa.email
}

output "image" {
  description = "Container image URI deployed for the serving service"
  value       = google_cloud_run_v2_service.dc_web_service.template[0].containers[0].image
}

