output "job_name" {
  value = google_cloud_run_v2_job.dc_data_job.name
}

output "run_db_init_id" {
  value = var.run_db_init ? null_resource.run_db_init[0].id : null
}
