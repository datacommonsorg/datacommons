output "redis_host" {
  value = google_redis_instance.redis_instance.host
}

output "redis_port" {
  value = google_redis_instance.redis_instance.port
}

output "connector_id" {
  value = try(google_vpc_access_connector.connector[0].id, null)
}
