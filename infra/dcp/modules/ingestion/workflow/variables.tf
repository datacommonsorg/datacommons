variable "deploy" {
  type = bool
}

variable "namespace" {
  type = string
}

variable "region" {
  type = string
}

variable "stateless_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for stateless resources (Workflows) to prevent accidental deletion."
}

variable "project_id" {
  type = string
}

variable "lock_acquisition_timeout" {
  type = number
}

variable "ingestion_helper_url" {
  type = string
}

variable "dataflow_service_account_email" {
  type = string
}

variable "enable_bigquery_postprocessing" {
  type    = bool
  default = false
}

variable "enable_datacommons_services" {
  type        = bool
  description = "Flag to indicate if datacommons_services is enabled"
  default     = true
}

variable "ingestion_helper_service_name" {
  type        = string
  description = "Name of the ingestion helper Cloud Run service"
  default     = ""
}

variable "enable_redis_cache_clearing" {
  type        = bool
  description = "Flag to enable Redis cache clearing"
  default     = false
}

variable "ingestion_artifacts_path" {
  type        = string
  description = "Path where pre-processed files are placed for the next stage"
}
