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
  google_maps_api_key           = null
  create_google_maps_key        = false
  google_maps_allowed_referrers = []
}

# -----------------------------------------------------------------------------
# Run 1: Default secret (what `datacommons-admin init` creates, and what every
# deployment from <= 1.1.7 already has): "<instance_name>-dc-api-key".
# -----------------------------------------------------------------------------
run "default_secret" {
  command = plan

  assert {
    condition = (
      data.google_secret_manager_secret.dc_api_key.project == "test-project" &&
      data.google_secret_manager_secret.dc_api_key.secret_id == "dev-dc-api-key"
    )
    error_message = "With no dc_api_key_secret_id, the module must look up projects/<project_id>/secrets/<instance_name>-dc-api-key"
  }
}

# -----------------------------------------------------------------------------
# Run 2: Default secret with no instance name -> "dc-api-key".
# -----------------------------------------------------------------------------
run "default_secret_no_instance_name" {
  command = plan

  variables {
    instance_name = ""
  }

  assert {
    condition     = data.google_secret_manager_secret.dc_api_key.secret_id == "dc-api-key"
    error_message = "With no instance_name, the default secret name must be dc-api-key"
  }
}

# -----------------------------------------------------------------------------
# Run 3: BYO secret, full resource path (may live in another project).
# -----------------------------------------------------------------------------
run "byo_secret_full_path" {
  command = plan

  variables {
    dc_api_key_secret_id = "projects/shared-secrets/secrets/team-dc-api-key"
  }

  assert {
    condition = (
      data.google_secret_manager_secret.dc_api_key.project == "shared-secrets" &&
      data.google_secret_manager_secret.dc_api_key.secret_id == "team-dc-api-key"
    )
    error_message = "A full resource path must be split into its project and secret name"
  }
}

# -----------------------------------------------------------------------------
# Run 4: BYO secret, short name -> resolved in project_id.
# -----------------------------------------------------------------------------
run "byo_secret_short_name" {
  command = plan

  variables {
    dc_api_key_secret_id = "custom-dc-api-key"
  }

  assert {
    condition = (
      data.google_secret_manager_secret.dc_api_key.project == "test-project" &&
      data.google_secret_manager_secret.dc_api_key.secret_id == "custom-dc-api-key"
    )
    error_message = "A short secret name must be resolved in project_id"
  }
}

# -----------------------------------------------------------------------------
# Run 5: The output is the looked-up secret's resource name.
# -----------------------------------------------------------------------------
run "output_is_secret_resource_name" {
  command = plan

  override_data {
    target = data.google_secret_manager_secret.dc_api_key
    values = {
      id = "projects/test-project/secrets/dev-dc-api-key"
    }
  }

  assert {
    condition     = output.dc_api_key_secret_id == "projects/test-project/secrets/dev-dc-api-key"
    error_message = "dc_api_key_secret_id output must be the secret's full resource name"
  }
}

# -----------------------------------------------------------------------------
# Run 6: Malformed secret IDs are rejected.
# -----------------------------------------------------------------------------
run "invalid_secret_id_rejected" {
  command = plan

  variables {
    dc_api_key_secret_id = "projects/test-project/secrets/a/versions/1"
  }

  expect_failures = [var.dc_api_key_secret_id]
}
