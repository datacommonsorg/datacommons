# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ==============================================================================
# Data Commons Platform (DCP) — Ephemeral Prober Infrastructure Module
# ==============================================================================
# Deploys:
#   1. Dedicated Prober Service Account with IAM bindings
#   2. Cloud Secret Manager secret for prober tfvars
#   3. Serverless Cloud Run Job for ephemeral prober container execution
#   4. Cloud Scheduler cron trigger
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.11.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required GCP APIs for Prober
resource "google_project_service" "prober_apis" {
  for_each = toset([
    "cloudscheduler.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "monitoring.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com"
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# 1. Prober Service Account
resource "google_service_account" "prober_sa" {
  account_id   = "${var.prober_name}-sa"
  display_name = "DCP Integration Prober Service Account"
  project      = var.project_id
}

# Project Owner & Service Account Token Creator Role Assignments for Prober Service Account
resource "google_project_iam_member" "prober_owner" {
  project = var.project_id
  role    = "roles/owner"
  member  = "serviceAccount:${google_service_account.prober_sa.email}"
}

resource "google_project_iam_member" "prober_token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.prober_sa.email}"
}

# 2. Secret Manager Secret for Prober Config / tfvars
resource "google_secret_manager_secret" "prober_tfvars" {
  secret_id = "${var.prober_name}-tfvars"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "prober_tfvars_version" {
  secret      = google_secret_manager_secret.prober_tfvars.id
  secret_data = <<EOF
# Data Commons Platform (DCP) Ephemeral Prober Configuration
project_id      = "${var.project_id}"
region          = "${var.region}"
prober_name     = "${var.prober_name}"
container_image = "${var.container_image}"
schedule        = "${var.schedule}"
test_config     = "${var.test_config}"
alert_email     = "${var.alert_email}"
EOF
}

# Secret Manager Secret for Data Commons API Key
resource "google_secret_manager_secret" "prober_api_key" {
  count     = var.dc_api_key != "" ? 1 : 0
  secret_id = "${var.prober_name}-api-key"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "prober_api_key_version" {
  count       = var.dc_api_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.prober_api_key[0].id
  secret_data = var.dc_api_key
}

resource "google_secret_manager_secret_iam_member" "prober_sa_api_key_accessor" {
  count     = var.dc_api_key != "" ? 1 : 0
  secret_id = google_secret_manager_secret.prober_api_key[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.prober_sa.email}"
}

# 3. GCS Bucket for Storing Historical Prober Reports
resource "google_storage_bucket" "prober_reports" {
  name                        = "${var.prober_name}-reports-${var.project_id}"
  location                    = var.region
  project                     = var.project_id
  force_destroy               = false
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

# 4. Cloud Run Job for Ephemeral Prober Execution
resource "google_cloud_run_v2_job" "prober_job" {
  name     = var.prober_name
  location = var.region
  project  = var.project_id

  template {
    labels = {
      "deploy-timestamp" = lower(replace(timestamp(), "/[^a-z0-9_-]/", "-"))
    }
    template {
      max_retries     = 0
      service_account = google_service_account.prober_sa.email
      timeout         = "3600s"

      containers {
        image = var.container_image

        args = [
          "--project", var.project_id,
          "--test-config", var.test_config,
          "--report-output", "gs://${google_storage_bucket.prober_reports.name}/reports/"
        ]

        dynamic "env" {
          for_each = var.dc_api_key != "" ? [1] : []
          content {
            name = "DC_API_KEY"
            value_source {
              secret_key_ref {
                secret  = google_secret_manager_secret.prober_api_key[0].secret_id
                version = "latest"
              }
            }
          }
        }

        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }
      }
    }
  }
}

# 4. Cloud Scheduler Trigger
resource "google_cloud_scheduler_job" "prober_cron" {
  name        = "${var.prober_name}-cron"
  description = "Triggers DCP Ephemeral Prober execution"
  schedule    = var.schedule
  time_zone   = "Etc/UTC"
  project     = var.project_id
  region      = var.region

  depends_on = [google_project_service.prober_apis]

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.prober_job.name}:run"

    oauth_token {
      service_account_email = google_service_account.prober_sa.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

# 5. Cloud Monitoring Notification Channel (Email)
resource "google_monitoring_notification_channel" "email" {
  count        = var.alert_email != "" ? 1 : 0
  display_name = "DCP Prober Alert Email"
  type         = "email"
  project      = var.project_id

  labels = {
    email_address = var.alert_email
  }
}

# 6. Log-Based Metric for Structured Prober Execution Failures
resource "google_logging_metric" "prober_failure_count" {
  name        = "${var.prober_name}_failure_count"
  project     = var.project_id
  description = "Log-based counter metric incremented whenever a DCP prober execution fails"

  filter = "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${google_cloud_run_v2_job.prober_job.name}\" AND jsonPayload.event_type=\"PROBER_EXECUTION_SUMMARY\" AND jsonPayload.status=\"FAILED\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# 7. Cloud Monitoring Alert Policy for Prober Execution Failures
resource "google_monitoring_alert_policy" "prober_failure" {
  display_name = "ALERT: DCP Prober Execution Failed"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Prober Execution Failure Event"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_job\" AND resource.label.job_name = \"${google_cloud_run_v2_job.prober_job.name}\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.prober_failure_count.name}\""
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  conditions {
    display_name = "Cloud Run Job Execution Failure"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_job\" AND resource.label.job_name = \"${google_cloud_run_v2_job.prober_job.name}\" AND metric.type = \"run.googleapis.com/job/completed_execution_count\" AND metric.label.result = \"failed\""
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].name] : []

  documentation {
    content   = "DCP Integration Prober job '${google_cloud_run_v2_job.prober_job.name}' failed on GCP project '${var.project_id}'. Check historical GCS reports at gs://${google_storage_bucket.prober_reports.name}/reports/"
    mime_type = "text/markdown"
  }
}
