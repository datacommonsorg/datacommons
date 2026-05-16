variable "project_id" {
  type = string
}

variable "namespace" {
  type = string
}

variable "region" {
  type = string
}

variable "deletion_protection" {
  type = bool
}

variable "dc_web_service_image" {
  type = string
}

variable "dc_web_service_cpu" {
  type = string
}

variable "dc_web_service_memory" {
  type = string
}

variable "dc_web_service_min_instance_count" {
  type = number
}

variable "dc_web_service_max_instance_count" {
  type = number
}

variable "make_dc_web_service_public" {
  type = bool
}

variable "google_analytics_tag_id" {
  type    = string
  default = null
}

variable "dc_search_scope" {
  type = string
}

variable "enable_mcp" {
  type = bool
}

variable "service_account_email" {
  type = string
}

variable "vpc_connector_id" {
  type = string
}

variable "use_spanner" {
  type = bool
}

variable "mysql_connection_name" {
  type    = string
  default = ""
}

variable "env_vars" {
  type = list(object({
    name  = string
    value = string
  }))
}

variable "secret_env_vars" {
  type = list(object({
    name    = string
    secret  = string
    version = string
  }))
}
