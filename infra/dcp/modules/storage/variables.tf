variable "enable_platform_service" {
  type = bool
}

variable "enable_datacommons_service" {
  type = bool
}

variable "project_id" {
  type = string
}

variable "namespace" {
  type = string
}

variable "deploy_pipeline" {
  type = bool
}

variable "create_pipeline_bucket" {
  type = bool
}

variable "pipeline_bucket_name" {
  type = string
}

variable "region" {
  type = string
}

variable "deletion_protection" {
  type = bool
}

variable "prep_bucket_name" {
  type = string
}

variable "prep_bucket_location" {
  type = string
}

variable "create_prep_bucket" {
  type    = bool
  default = true
}

variable "orchestrator_email" {
  type        = string
  description = "Email of the orchestrator service account"
  default     = ""
}
