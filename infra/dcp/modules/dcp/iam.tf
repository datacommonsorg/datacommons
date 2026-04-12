# Service Account for the Cloud Run service
resource "google_service_account" "dcp_runner" {
  account_id   = "${local.name_prefix}${var.service_account_name}"
  display_name = "Data Commons Platform Runner"
}

# Grant Spanner Database User role to the Service Account
resource "google_project_iam_member" "spanner_user" {
  project = var.project_id
  role    = "roles/spanner.databaseUser"
  member  = "serviceAccount:${google_service_account.dcp_runner.email}"
}

# Make the Cloud Run service public (optional, can be restricted)
resource "google_cloud_run_service_iam_binding" "public_invoker" {
  count    = var.make_service_public ? 1 : 0
  location = google_cloud_run_v2_service.dcp_service.location
  service  = google_cloud_run_v2_service.dcp_service.name
  role     = "roles/run.invoker"
  members = [
    "allUsers"
  ]
}
