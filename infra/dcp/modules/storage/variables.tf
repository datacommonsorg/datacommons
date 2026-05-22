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

variable "deletion_protection" {
  type = bool
}

