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

variable "stateless_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for stateless resources (Cloud Run) to prevent accidental deletion."
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

variable "enable_bigquery_connection" {
  type        = bool
  description = "Flag to enable BigQuery connection usage"
  default     = false
}

variable "enable_bigquery_postprocessing" {
  type        = bool
  description = "Flag to enable BigQuery postprocessing"
  default     = true
}

variable "enable_embedding_ingestion" {
  type        = bool
  description = "Flag to enable embedding ingestion"
  default     = false
}

variable "vpc_connector_id" {
  type        = string
  description = "VPC access connector ID for Cloud Run"
  default     = ""
}

variable "redis_host" {
  type        = string
  description = "Redis host IP"
  default     = ""
}

variable "redis_port" {
  type        = string
  description = "Redis port"
  default     = "6379"
}

variable "ingestion_artifacts_path" {
  type        = string
  description = "Path where pre-processed files are placed for the next stage"
}

