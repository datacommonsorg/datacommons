output "job_name" {
  value = google_cloud_run_v2_job.dc_postprocessing_job.name
}

output "service_account_email" {
  value = google_service_account.postprocessing_sa.email
}
