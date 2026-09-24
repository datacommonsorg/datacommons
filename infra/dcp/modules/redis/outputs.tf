output "redis_host" {
  value = google_redis_instance.redis_instance.host
}

output "redis_port" {
  value = google_redis_instance.redis_instance.port
}

output "redis_auth_secret_id" {
  description = "The Secret Manager secret ID holding the Redis AUTH string, or null if enable_auth is false"
  value       = var.enable_auth ? google_secret_manager_secret.redis_auth[0].secret_id : null
}
