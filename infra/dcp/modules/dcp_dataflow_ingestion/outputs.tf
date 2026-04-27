output "ingestion_runner_email" {
  value = var.deploy ? google_service_account.dcp_ingestion_runner[0].email : null
}

output "ingestion_runner_id" {
  value = var.deploy ? google_service_account.dcp_ingestion_runner[0].id : null
}

output "ingestion_helper_uri" {
  value = var.deploy ? google_cloud_run_v2_service.ingestion_helper[0].uri : null
}
