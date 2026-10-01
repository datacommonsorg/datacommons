variable "deploy" {
  type = bool
}

variable "project_id" {
  type = string
}

variable "instance_name" {
  type = string
}

variable "ingestion_bucket_name" {
  type = string
}

variable "spanner_instance_id" {
  type        = string
  description = "Optional Cloud Spanner instance ID"
  default     = null
}

variable "spanner_database_id" {
  type        = string
  description = "Optional Cloud Spanner database ID"
  default     = null
}
