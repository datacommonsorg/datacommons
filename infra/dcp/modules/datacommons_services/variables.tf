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

variable "image" {
  type = string
}

variable "cpu" {
  type = string
}

variable "memory" {
  type = string
}

variable "min_instances" {
  type = number
}

variable "max_instances" {
  type = number
}

variable "make_public" {
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

variable "artifacts_bucket_name" {
  type        = string
  description = "Name of the unified GCS bucket for artifacts"
  default     = ""
}

variable "mcp_instructions_path" {
  type        = string
  description = "Path within the unified storage bucket for customized instructions for server tools and agents"
  default     = null
}
