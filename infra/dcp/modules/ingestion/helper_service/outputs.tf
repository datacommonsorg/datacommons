output "ingestion_helper_url" {
  value = var.deploy ? google_cloud_run_v2_service.ingestion_helper[0].uri : null
}

output "service_account_email" {
  value = var.deploy ? google_service_account.helper_sa[0].email : null
}

output "image" {
  description = "Container image URI deployed for the ingestion helper service"
  value       = var.deploy ? google_cloud_run_v2_service.ingestion_helper[0].template[0].containers[0].image : null
}

