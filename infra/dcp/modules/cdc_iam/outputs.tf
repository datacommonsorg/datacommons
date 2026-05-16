output "service_account_email" {
  value = google_service_account.datacommons_service_account.email
}

output "dc_api_key_secret_id" {
  value = google_secret_manager_secret_version.dc_api_key_version.secret
}

output "maps_api_key_secret_id" {
  value = var.disable_google_maps ? "" : google_secret_manager_secret_version.maps_api_key_version[0].secret
}
