# =============================================================================
# Ingestion Preprocessing Job Infrastructure
# =============================================================================
# Cloud Batch does not maintain static deployed job instances; jobs are launched
# dynamically on-demand by Cloud Workflows during each ingestion execution.
#
# This submodule does not manage job execution or deployment logic. It is
# maintained to provision and manage the IAM permissions, Service Account, and
# Secret Manager access required by the preprocessing worker container.
# =============================================================================

locals {
  name_prefix = var.instance_name != "" ? "${var.instance_name}-" : ""
}

resource "google_service_account" "preprocessing_sa" {
  account_id   = "${local.name_prefix}dc-ing-pre-sa"
  display_name = "Data Commons Ingestion Preprocessing SA"
}

resource "google_project_iam_member" "preprocessing_batch_agent" {
  project = var.project_id
  role    = "roles/batch.agentReporter"
  member  = "serviceAccount:${google_service_account.preprocessing_sa.email}"
}

resource "google_project_iam_member" "preprocessing_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.preprocessing_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "preprocessing_secret_accessor" {
  for_each = { for k, v in var.env_secrets : k => v if v.enabled }

  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.preprocessing_sa.email}"
}
