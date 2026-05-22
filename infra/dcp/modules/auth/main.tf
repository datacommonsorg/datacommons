locals {
  name_prefix               = var.namespace != "" ? "${var.namespace}-" : ""
  google_maps_api_key_value = var.google_maps_api_key != null ? var.google_maps_api_key : try(google_apikeys_key.maps_api_key[0].key_string, "")
}




resource "google_secret_manager_secret" "dc_api_key" {
  secret_id = "${local.name_prefix}dc-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "dc_api_key_version" {
  secret      = google_secret_manager_secret.dc_api_key.id
  secret_data = var.dc_api_key
}

# Random ID suffix to avoid name conflicts when recreating keys in recovery state.
resource "random_id" "api_key_suffix" {
  byte_length = 4
}

resource "google_apikeys_key" "maps_api_key" {
  count        = var.google_maps_api_key == null && var.create_google_maps_key ? 1 : 0

  name         = "${local.name_prefix}dc-google-maps-key-${random_id.api_key_suffix.hex}"
  display_name = "Maps API Key for ${var.namespace != "" ? var.namespace : "Data Commons"}"
  project      = var.project_id



  restrictions {
    api_targets {
      service = "maps-backend.googleapis.com"
    }
    api_targets {
      service = "places_backend"
    }
  }
}

resource "google_secret_manager_secret" "maps_api_key" {
  count     = (var.google_maps_api_key != null || var.create_google_maps_key) ? 1 : 0


  secret_id = "${local.name_prefix}dc-google-maps-api-key-${random_id.api_key_suffix.hex}"

  replication {
    auto {}
  }
}


resource "google_secret_manager_secret_version" "maps_api_key_version" {
  count       = (var.google_maps_api_key != null || var.create_google_maps_key) ? 1 : 0


  secret      = google_secret_manager_secret.maps_api_key[0].id
  secret_data = local.google_maps_api_key_value
}

