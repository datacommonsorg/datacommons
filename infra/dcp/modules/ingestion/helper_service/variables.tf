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

variable "image" {
  type    = string
  default = "gcr.io/datcom-ci/datacommons-ingestion-helper:latest"
}

variable "bigquery_connection_id" {
  type    = string
  default = ""
}

variable "use_spanner" {
  type    = bool
  default = true
}

variable "bigquery_job_service_account" {
  type        = string
  description = "Service account email to impersonate for BigQuery jobs"
  default     = ""
}
