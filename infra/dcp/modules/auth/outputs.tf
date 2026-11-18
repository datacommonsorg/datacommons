
output "dc_api_key_secret_id" {
  description = "Full resource name (projects/<project>/secrets/<name>) of the Secret Manager secret holding the Data Commons API key."
  value       = data.google_secret_manager_secret.dc_api_key.id
}

output "maps_api_key_secret_id" {
  value = try(google_secret_manager_secret_version.maps_api_key_version[0].secret, "")
}
