output "ingestion_helper_url" {
  description = "URL of the ingestion helper Cloud Run service"
  value       = google_cloud_run_v2_service.ingestion_helper.uri
}

output "service_name" {
  description = "Name of the ingestion helper Cloud Run service"
  value       = google_cloud_run_v2_service.ingestion_helper.name
}

output "service_account_email" {
  description = "Email of the ingestion helper service account"
  value       = google_service_account.helper_sa.email
}

output "image" {
  description = "Container image URI deployed for the ingestion helper service"
  value       = google_cloud_run_v2_service.ingestion_helper.template[0].containers[0].image
}

