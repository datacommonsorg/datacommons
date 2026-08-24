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

variable "project_id" {
  type        = string
  description = "GCP Project ID"
  default     = "datcom-dcp"
}

variable "region" {
  type        = string
  description = "GCP Region"
  default     = "us-central1"
}

variable "prober_name" {
  type        = string
  description = "Name prefix for prober infrastructure resources"
  default     = "dcp-prober"
}

variable "container_image" {
  type        = string
  description = "Container image URI for prober (stored in datcom-ci registry)"
  default     = "us-docker.pkg.dev/datcom-ci/datcom-tools/datacommons-platform-prober:latest"
}

variable "schedule" {
  type        = string
  description = "Cron schedule for prober execution"
  default     = "0 */1 * * *"
}

variable "test_config" {
  type        = string
  description = "Default dataset test spec name"
  default     = "foobar_wages"
}

variable "alert_email" {
  type        = string
  description = "Notification email address for prober failure alerts"
  default     = ""
}

variable "dc_api_key" {
  type        = string
  description = "Data Commons API Key for prober infrastructure"
  default     = ""
  sensitive   = true
}
