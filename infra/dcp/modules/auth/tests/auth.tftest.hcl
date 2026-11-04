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

# Unit tests for the auth module (infra/dcp/modules/auth/main.tf).

mock_provider "google" {}
mock_provider "random" {}

variables {
  project_id                    = "test-project"
  instance_name                 = "dev"
  dc_api_key_secret_id          = ""
  dc_api_key                    = ""
  google_maps_api_key           = null
  create_google_maps_key        = false
  google_maps_allowed_referrers = []
}

# -----------------------------------------------------------------------------
# Run 1: BYO / CLI-Provisioned Secret Manager ID (Full Resource Path)
# -----------------------------------------------------------------------------
run "external_secret_full_path" {
  command = plan

  variables {
    dc_api_key_secret_id = "projects/test-project/secrets/dev-dc-api-key"
  }

  # When dc_api_key_secret_id is provided, Terraform must NOT create a managed secret or version.
  assert {
    condition     = length(google_secret_manager_secret.dc_api_key) == 0 && length(google_secret_manager_secret_version.dc_api_key_version) == 0
    error_message = "Managed Secret Manager resources must be skipped (count = 0) when dc_api_key_secret_id is provided"
  }

  # Output must pass through the full resource path unchanged.
  assert {
    condition     = output.dc_api_key_secret_id == "projects/test-project/secrets/dev-dc-api-key"
    error_message = "dc_api_key_secret_id output must equal the provided full resource path"
  }
}

# -----------------------------------------------------------------------------
# Run 2: BYO Secret Manager ID (Short Secret Name Normalization)
# -----------------------------------------------------------------------------
run "external_secret_short_name" {
  command = plan

  variables {
    dc_api_key_secret_id = "custom-dc-api-key"
  }

  assert {
    condition     = length(google_secret_manager_secret.dc_api_key) == 0 && length(google_secret_manager_secret_version.dc_api_key_version) == 0
    error_message = "Managed Secret Manager resources must be skipped (count = 0) when a short dc_api_key_secret_id is provided"
  }

  # Short secret names must be normalized to projects/<project_id>/secrets/<name>.
  assert {
    condition     = output.dc_api_key_secret_id == "projects/test-project/secrets/custom-dc-api-key"
    error_message = "Short dc_api_key_secret_id must be normalized to projects/<project_id>/secrets/<secret_name>"
  }
}

# -----------------------------------------------------------------------------
# Run 3: Legacy Fallback (dc_api_key Provided, dc_api_key_secret_id Empty)
# -----------------------------------------------------------------------------
run "legacy_plaintext_dc_api_key" {
  command = plan

  variables {
    dc_api_key_secret_id = ""
    dc_api_key           = "legacy-api-key-value"
  }

  # When dc_api_key_secret_id is empty, Terraform manages the secret with deletion_policy = "ABANDON".
  assert {
    condition = (
      length(google_secret_manager_secret.dc_api_key) == 1 &&
      google_secret_manager_secret.dc_api_key[0].secret_id == "dev-dc-api-key" &&
      google_secret_manager_secret.dc_api_key[0].deletion_policy == "ABANDON"
    )
    error_message = "Legacy dc_api_key must provision google_secret_manager_secret.dc_api_key[0] with deletion_policy = ABANDON"
  }

  assert {
    condition = (
      length(google_secret_manager_secret_version.dc_api_key_version) == 1 &&
      nonsensitive(google_secret_manager_secret_version.dc_api_key_version[0].secret_data) == "legacy-api-key-value" &&
      google_secret_manager_secret_version.dc_api_key_version[0].deletion_policy == "ABANDON"
    )
    error_message = "Legacy dc_api_key must provision google_secret_manager_secret_version.dc_api_key_version[0] with deletion_policy = ABANDON"
  }
}
