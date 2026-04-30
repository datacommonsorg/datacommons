output "mysql_instance_connection_name" {
  value = google_sql_database_instance.mysql_instance.connection_name
}

output "mysql_instance_public_ip" {
  value = google_sql_database_instance.mysql_instance.public_ip_address
}

output "mysql_user" {
  value     = var.mysql_user
  sensitive = true
}

output "mysql_user_password" {
  value     = random_password.mysql_password.result
  sensitive = true
}

output "mysql_password_secret_id" {
  value = google_secret_manager_secret.mysql_password_secret.id
}
