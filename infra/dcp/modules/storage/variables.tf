variable "project_id" {
  type = string
}

variable "namespace" {
  type = string
}

variable "deploy_workflow" {
  type = bool
}

variable "create_workflow_bucket" {
  type = bool
}

variable "ingestion_workflow_bucket_name" {
  type = string
}

variable "region" {
  type = string
}

variable "deletion_protection" {
  type = bool
}

variable "ingestion_input_bucket_name" {
  type = string
}

variable "input_bucket_location" {
  type = string
}

variable "create_input_bucket" {
  type    = bool
  default = true
}

variable "orchestrator_email" {
  type        = string
  description = "Email of the orchestrator service account"
  default     = ""
}
