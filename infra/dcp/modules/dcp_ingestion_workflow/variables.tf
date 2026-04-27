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
