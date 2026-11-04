
output "dc_api_key_secret_id" {
  value = local.normalized_dc_api_key_secret_id != "" ? local.normalized_dc_api_key_secret_id : google_secret_manager_secret_version.dc_api_key_version[0].secret
}

output "maps_api_key_secret_id" {
  value = try(google_secret_manager_secret_version.maps_api_key_version[0].secret, "")
}
