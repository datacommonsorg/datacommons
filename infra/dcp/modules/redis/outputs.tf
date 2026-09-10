output "redis_host" {
  value = google_redis_instance.redis_instance.host
}

output "redis_port" {
  value = google_redis_instance.redis_instance.port
}
