# Custom Data Commons service account
resource "google_service_account" "datacommons_service_account" {
  account_id   = "${var.namespace}-datacommons-sa"
  display_name = "Data Commons Service Account for ${var.project_id} (namespace = ${var.namespace})"
}

resource "google_project_iam_member" "datacommons_service_account_roles" {
  for_each = toset(["roles/compute.networkViewer", "roles/redis.editor", "roles/cloudsql.admin", "roles/storage.objectAdmin", "roles/run.admin", "roles/vpcaccess.user", "roles/iam.serviceAccountUser", "roles/secretmanager.secretAccessor"])
  project  = var.project_id
  member   = "serviceAccount:${google_service_account.datacommons_service_account.email}"
  role     = each.value
}

resource "google_secret_manager_secret" "dc_api_key" {
  secret_id = "${var.namespace}-dc-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "dc_api_key_version" {
  secret      = google_secret_manager_secret.dc_api_key.id
  secret_data = var.dc_api_key
}
