variable "namespace" {
  type = string
}

variable "region" {
  type = string
}

variable "mysql_instance_name" {
  type = string
}

variable "mysql_database_name" {
  type = string
}

variable "mysql_database_version" {
  type = string
}

variable "mysql_cpu_count" {
  type = number
}

variable "mysql_memory_size_mb" {
  type = number
}

variable "mysql_user" {
  type = string
}

variable "deletion_protection" {
  type = bool
}
