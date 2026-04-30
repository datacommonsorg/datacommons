variable "namespace" {
  type = string
}

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "image_url" {
  type = string
}

variable "service_name" {
  type = string
}

variable "service_account_name" {
  type = string
}

variable "service_cpu" {
  type = string
}

variable "service_memory" {
  type = string
}

variable "service_min_instances" {
  type = number
}

variable "service_max_instances" {
  type = number
}

variable "service_concurrency" {
  type = number
}

variable "service_timeout_seconds" {
  type = number
}

variable "deletion_protection" {
  type = bool
}

variable "make_service_public" {
  type = bool
}

variable "spanner_instance_id" {
  type = string
}

variable "spanner_database_id" {
  type = string
}
