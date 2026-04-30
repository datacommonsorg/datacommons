locals {
  name_prefix        = var.namespace != "" ? "${var.namespace}-" : ""
  maps_api_key_value = var.maps_api_key != null ? var.maps_api_key : try(google_apikeys_key.maps_api_key[0].key_string, "")
}

resource "google_service_account" "datacommons_service_account" {
  account_id   = "${local.name_prefix}datacommons-sa"
  display_name = "Data Commons Service Account for ${var.project_id}${var.namespace != "" ? " (namespace = ${var.namespace})" : ""}"
}

resource "google_project_iam_member" "datacommons_service_account_roles" {
  for_each = setsubtract(toset([
    "roles/compute.networkViewer",
    "roles/redis.editor",
    "roles/cloudsql.admin",
    "roles/storage.objectAdmin",
    "roles/run.admin",
    "roles/vpcaccess.user",
    "roles/iam.serviceAccountUser",
    "roles/secretmanager.secretAccessor",
    "roles/spanner.databaseUser"
  ]), var.use_spanner ? [] : ["roles/spanner.databaseUser"])

  project = var.project_id
  member  = "serviceAccount:${google_service_account.datacommons_service_account.email}"
  role    = each.value
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

resource "google_apikeys_key" "maps_api_key" {
  count        = var.maps_api_key == null && !var.disable_google_maps ? 1 : 0
  name         = "${local.name_prefix}maps-key"
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
  count     = var.disable_google_maps ? 0 : 1
  secret_id = "${local.name_prefix}maps-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "maps_api_key_version" {
  count       = var.disable_google_maps ? 0 : 1
  secret      = google_secret_manager_secret.maps_api_key[0].id
  secret_data = local.maps_api_key_value
}
