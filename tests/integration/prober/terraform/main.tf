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

# 1. Prober Service Account
resource "google_service_account" "prober_sa" {
  account_id   = "${var.prober_name}-sa"
  display_name = "DCP Integration Prober Service Account"
  project      = var.project_id
}

# IAM Role Assignments for Prober Service Account
resource "google_project_iam_member" "prober_roles" {
  for_each = toset([
    "roles/spanner.admin",
    "roles/workflows.admin",
    "roles/run.admin",
    "roles/storage.admin",
    "roles/iam.serviceAccountTokenCreator",
    "roles/secretmanager.admin",
    "roles/resourcemanager.projectIamAdmin"
  ])

  project = var.project_id
  role    = each.key
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
EOF
}

# 3. Cloud Run Job for Ephemeral Prober Execution
resource "google_cloud_run_v2_job" "prober_job" {
  name     = var.prober_name
  location = var.region
  project  = var.project_id

  template {
    template {
      service_account = google_service_account.prober_sa.email
      timeout         = "3600s"

      containers {
        image = var.container_image

        args = [
          "--project", var.project_id,
          "--test-config", var.test_config,
          "--report-output", "gs://dcp-prober-reports-${var.project_id}/reports/"
        ]

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

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.prober_job.name}:run"

    oauth_token {
      service_account_email = google_service_account.prober_sa.email
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

# 6. Cloud Monitoring Alert Policy for Prober Execution Failures
resource "google_monitoring_alert_policy" "prober_failure" {
  display_name = "ALERT: DCP Prober Execution Failed"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run Job Execution Failure"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_job\" AND resource.label.job_name = \"${google_cloud_run_v2_job.prober_job.name}\" AND metric.type = \"run.googleapis.com/job/completed_execution_count\" AND metric.label.result = \"failed\""
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].name] : []

  documentation {
    content   = "DCP Integration Prober job '${google_cloud_run_v2_job.prober_job.name}' failed on GCP project '${var.project_id}'. Check historical GCS reports at gs://dcp-prober-reports-${var.project_id}/reports/"
    mime_type = "text/markdown"
  }
}

# Outputs
output "prober_service_account_email" {
  value       = google_service_account.prober_sa.email
  description = "Prober Service Account Email"
}

output "prober_cloud_run_job_name" {
  value       = google_cloud_run_v2_job.prober_job.name
  description = "Cloud Run Job Name"
}

output "prober_scheduler_job_name" {
  value       = google_cloud_scheduler_job.prober_cron.name
  description = "Cloud Scheduler Job Name"
}
