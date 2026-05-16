locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
}

resource "random_id" "mysql_suffix" {
  byte_length = 4
}

resource "google_sql_database_instance" "mysql_instance" {
  name             = "${local.name_prefix}${var.mysql_instance_name}-${random_id.mysql_suffix.hex}"
  database_version = var.mysql_database_version
  region           = var.region

  settings {
    tier = "db-custom-${var.mysql_cpu_count}-${var.mysql_memory_size_mb}"
    ip_configuration {
      ipv4_enabled = true
    }
    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = var.deletion_protection
}

resource "google_sql_database" "mysql_db" {
  name     = var.mysql_database_name
  instance = google_sql_database_instance.mysql_instance.name
}

resource "random_password" "mysql_password" {
  length  = 16
  special = true
}

resource "google_secret_manager_secret" "mysql_password_secret" {
  secret_id = "${local.name_prefix}mysql-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "mysql_password_secret_version" {
  secret      = google_secret_manager_secret.mysql_password_secret.id
  secret_data = random_password.mysql_password.result
}

resource "google_sql_user" "mysql_user" {
  name     = var.mysql_user
  instance = google_sql_database_instance.mysql_instance.name
  password = random_password.mysql_password.result
}
