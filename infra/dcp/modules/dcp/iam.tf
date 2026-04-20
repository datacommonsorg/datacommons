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

# Dedicated Service Account for running the Dataflow Ingestion pipeline
resource "google_service_account" "dcp_ingestion_runner" {
  count        = var.deploy_data_ingestion_workflow ? 1 : 0
  account_id   = "${local.name_prefix}dcp-ingestion-sa"
  display_name = "Data Commons Platform Ingestion Runner"
}

# Grant Spanner Database User access to the Ingestion runner
resource "google_project_iam_member" "ingestion_spanner_user" {
  count   = var.deploy_data_ingestion_workflow ? 1 : 0
  project = var.project_id
  role    = "roles/spanner.databaseUser"
  member  = "serviceAccount:${google_service_account.dcp_ingestion_runner[0].email}"
}

# Grant Dataflow orchestration and Storage permissions exclusively to the new Ingestion runner
resource "google_project_iam_member" "dataflow_admin" {
  count   = var.deploy_data_ingestion_workflow ? 1 : 0
  project = var.project_id
  role    = "roles/dataflow.admin"
  member  = "serviceAccount:${google_service_account.dcp_ingestion_runner[0].email}"
}

resource "google_project_iam_member" "dataflow_worker" {
  count   = var.deploy_data_ingestion_workflow ? 1 : 0
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.dcp_ingestion_runner[0].email}"
}


resource "google_service_account_iam_member" "service_account_user" {
  count              = var.deploy_data_ingestion_workflow ? 1 : 0
  service_account_id = google_service_account.dcp_ingestion_runner[0].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.dcp_ingestion_runner[0].email}"
}

# Fetch project number to reference the Workflows background Service Agent
data "google_project" "project" {
  project_id = var.project_id
}

resource "google_service_account_iam_member" "workflows_token_creator" {
  count              = var.deploy_data_ingestion_workflow ? 1 : 0
  service_account_id = google_service_account.dcp_ingestion_runner[0].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-workflows.iam.gserviceaccount.com"
}

# Bind Object Admin access to either the newly created bucket or an explicitly reused external one
resource "google_storage_bucket_iam_member" "dynamic_ingestion_bucket_access" {
  count  = var.deploy_data_ingestion_workflow ? 1 : 0
  bucket = var.create_ingestion_bucket ? google_storage_bucket.data_ingestion_bucket[0].name : var.external_ingestion_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dcp_ingestion_runner[0].email}"
}

# Grant Workflows permission to invoke the ingestion helper
resource "google_cloud_run_service_iam_member" "ingestion_helper_invoker" {
  count    = var.deploy_data_ingestion_workflow ? 1 : 0
  location = google_cloud_run_v2_service.ingestion_helper[0].location
  service  = google_cloud_run_v2_service.ingestion_helper[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.dcp_ingestion_runner[0].email}"
}
