variable "deploy" {
  type = bool
}

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

variable "spanner_instance_id" {
  type = string
}

variable "spanner_database_id" {
  type = string
}

variable "ingestion_bucket_name" {
  type = string
}

variable "service_account_email" {
  type = string
}

variable "ingestion_helper_image" {
  type    = string
  default = "gcr.io/datcom-ci/datacommons-ingestion-helper:latest"
}

variable "orchestrator_email" {
  type        = string
  description = "Email of the orchestrator service account"
  default     = ""
}

variable "bq_connection_id" {
  type    = string
  default = ""
}
