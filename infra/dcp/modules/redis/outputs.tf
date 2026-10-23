output "redis_host" {
  value = google_redis_instance.redis_instance.host
}

output "redis_port" {
  value = google_redis_instance.redis_instance.port
}

output "redis_auth_secret_id" {
  description = "The Secret Manager secret ID holding the Redis AUTH string, or null if enable_auth is false"
  value       = var.enable_auth ? google_secret_manager_secret.redis_auth[0].secret_id : null
  depends_on  = [google_secret_manager_secret_version.redis_auth_version]
}

output "redis_ca_cert" {
  description = "The PEM-encoded CA certificate(s) for the Redis instance when enable_tls is true, or empty string otherwise"
  value       = var.enable_tls ? join("\n", [for ca in google_redis_instance.redis_instance.server_ca_certs : ca.cert]) : ""
}
