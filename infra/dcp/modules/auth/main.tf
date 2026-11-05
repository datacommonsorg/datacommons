locals {
  name_prefix               = var.instance_name != "" ? "${var.instance_name}-" : ""
  google_maps_api_key_value = var.google_maps_api_key != null ? var.google_maps_api_key : try(google_apikeys_key.maps_api_key[0].key_string, "")

  # The Data Commons API key lives in Secret Manager in project_id and is never
  # managed by Terraform. `datacommons-admin init` creates
  # "<instance_name>-dc-api-key" by default; dc_api_key_secret_id overrides the
  # secret name.
  dc_api_key_secret_name = var.dc_api_key_secret_id != "" ? var.dc_api_key_secret_id : "${local.name_prefix}dc-api-key"
}

# Fails with a clear "not found" error if the secret is missing, before
# Cloud Run or the ingestion jobs try to use it.
data "google_secret_manager_secret" "dc_api_key" {
  project   = var.project_id
  secret_id = local.dc_api_key_secret_name
}

# Releases <= 1.1.7 created the Data Commons API key secret (and a version
# holding the plaintext key) in Terraform. Stop managing them WITHOUT deleting
# them: the live secret keeps serving, and the plaintext leaves Terraform state.
# A `removed` block (rather than count = 0 + deletion_policy) is required so
# this is safe even on the very first apply of the new release.
removed {
  from = google_secret_manager_secret.dc_api_key

  lifecycle {
    destroy = false
  }
}

removed {
  from = google_secret_manager_secret_version.dc_api_key_version

  lifecycle {
    destroy = false
  }
}

# Random ID suffix to avoid name conflicts when recreating keys in recovery state.
resource "random_id" "api_key_suffix" {
  byte_length = 4
}

resource "google_apikeys_key" "maps_api_key" {
  count = var.google_maps_api_key == null && var.create_google_maps_key ? 1 : 0

  name         = "${local.name_prefix}dc-google-maps-key-${random_id.api_key_suffix.hex}"
  display_name = "Maps API Key for ${var.instance_name != "" ? var.instance_name : "Data Commons"}"
  project      = var.project_id

  restrictions {
    api_targets {
      service = "maps-backend.googleapis.com"
    }
    api_targets {
      service = "places_backend"
    }

    dynamic "browser_key_restrictions" {
      for_each = length(var.google_maps_allowed_referrers) > 0 ? [1] : []
      content {
        allowed_referrers = var.google_maps_allowed_referrers
      }
    }
  }
}

resource "google_secret_manager_secret" "maps_api_key" {
  count = (var.google_maps_api_key != null || var.create_google_maps_key) ? 1 : 0

  secret_id = "${local.name_prefix}dc-google-maps-api-key-${random_id.api_key_suffix.hex}"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "maps_api_key_version" {
  count = (var.google_maps_api_key != null || var.create_google_maps_key) ? 1 : 0

  secret      = google_secret_manager_secret.maps_api_key[0].id
  secret_data = local.google_maps_api_key_value
}

