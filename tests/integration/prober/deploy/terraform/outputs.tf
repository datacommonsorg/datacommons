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

output "prober_tfvars_secret_id" {
  value       = google_secret_manager_secret.prober_tfvars.secret_id
  description = "GCP Secret Manager Secret ID containing terraform.tfvars"
}
