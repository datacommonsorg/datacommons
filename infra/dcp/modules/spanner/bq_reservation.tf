# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Create the BigQuery Reservation for Federation queries
resource "google_bigquery_reservation" "default" {
  count         = var.create_spanner_db && var.enable_bq_federation ? 1 : 0
  name          = "default"
  location      = var.region
  edition       = "ENTERPRISE"
  slot_capacity = 100

  autoscale {
    max_slots = 400
  }
}

# Assign the reservation to the project for queries
resource "google_bigquery_reservation_assignment" "project_assignment" {
  count       = var.create_spanner_db && var.enable_bq_federation ? 1 : 0
  reservation = google_bigquery_reservation.default[0].id
  assignee    = "projects/${var.project_id}"
  job_type    = "QUERY"
}
