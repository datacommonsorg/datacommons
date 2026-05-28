variable "project_id" {
  type = string
}

variable "namespace" {
  type = string
}

variable "create_artifacts_bucket" {
  type    = bool
  default = true
}

variable "artifacts_bucket_name" {
  type = string
}

variable "region" {
  type = string
}

variable "stateful_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for stateful resources (GCS) to prevent data loss."
}

variable "foundation_dependency" {
  description = "An artificial dependency to delay resource creation until APIs are ready."
  type        = any
  default     = null
}

