output "ingestion_helper_uri" {
  value = var.deploy ? google_cloud_run_v2_service.ingestion_helper[0].uri : null
}
