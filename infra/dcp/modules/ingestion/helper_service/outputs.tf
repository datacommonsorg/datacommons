output "ingestion_helper_url" {
  value = google_cloud_run_v2_service.ingestion_helper.uri
}

output "service_account_email" {
  value = google_service_account.helper_sa.email
}

output "image" {
  description = "Container image URI deployed for the ingestion helper service"
  value       = google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].image
}

