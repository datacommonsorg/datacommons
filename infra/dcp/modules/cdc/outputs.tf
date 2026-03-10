output "redis_instance_host" {
  description = "The hostname or IP address of the Redis instance"
  value       = try(local.redis_instance.host, "")
}

output "redis_instance_port" {
  description = "The port number the Redis instance is listening on"
  value       = try(local.redis_instance.port, "")
}

output "mysql_instance_connection_name" {
  description = "The connection name of the MySQL instance"
  value       = google_sql_database_instance.mysql_instance.connection_name
}

output "mysql_instance_public_ip" {
  description = "The public IP address of the MySQL instance"
  value       = google_sql_database_instance.mysql_instance.public_ip_address
}

output "mysql_user" {
  description = "MySQL user name"
  value       = var.mysql_user
  sensitive   = true
}

output "mysql_user_password" {
  description = "The password for the MySQL user"
  value       = random_password.mysql_password.result
  sensitive   = true
}

output "gcs_data_bucket_name" {
  value = local.gcs_data_bucket_name
}

output "cloud_run_service_name" {
  description = "Name of the Data Commons Cloud Run Web service"
  value       = google_cloud_run_v2_service.dc_web_service.name
}

output "cloud_run_service_url" {
  description = "URL of the Data Commons Cloud Run Web service"
  value       = google_cloud_run_v2_service.dc_web_service.uri
}
