# =============================================================================
# Serving Layer - Platform Service Outputs (Experimental)
# =============================================================================

output "platform_service_url" {
  description = "Cloud Run service URL for the platform service."
  value       = google_cloud_run_v2_service.service.uri
}
