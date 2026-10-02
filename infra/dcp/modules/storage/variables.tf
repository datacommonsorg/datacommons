variable "project_id" {
  type = string
}

variable "instance_name" {
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

variable "enable_versioning" {
  type        = bool
  default     = true
  description = "Enable object versioning on the artifacts bucket."
}

