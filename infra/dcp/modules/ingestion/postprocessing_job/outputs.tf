output "job_name" {
  value = google_cloud_run_v2_job.dc_postprocessing_job.name
}

output "service_account_email" {
  value = google_service_account.postprocessing_sa.email
}

output "image" {
  description = "Container image URI deployed for the postprocessing job"
  value       = google_cloud_run_v2_job.dc_postprocessing_job.template[0].template[0].containers[0].image
}

