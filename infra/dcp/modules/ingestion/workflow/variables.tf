variable "deploy" {
  type = bool
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

variable "project_id" {
  type = string
}

variable "lock_acquisition_timeout" {
  type = number
}

variable "ingestion_helper_uri" {
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
