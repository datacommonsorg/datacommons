output "service_account_email" {
  value = google_service_account.datacommons_service_account.email
}

output "dc_api_key_secret_id" {
  value = google_secret_manager_secret.dc_api_key.secret_id
}

output "maps_api_key_secret_id" {
  value = var.disable_google_maps ? "" : google_secret_manager_secret.maps_api_key[0].secret_id
}
