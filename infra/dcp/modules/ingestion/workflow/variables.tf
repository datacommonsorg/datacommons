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

variable "ingestion_lock_timeout" {
  type = number
}

variable "ingestion_helper_uri" {
  type = string
}

variable "ingestion_runner_id" {
  type = string
}

variable "ingestion_runner_email" {
  type = string
}

variable "orchestrator_email" {
  type        = string
  description = "Email of the orchestrator service account"
  default     = ""
}

variable "enable_bq_federation" {
  type    = bool
  default = false
}

variable "enable_datacommons_services" {
  type        = bool
  description = "Flag to indicate if datacommons_services is enabled"
  default     = true
}
