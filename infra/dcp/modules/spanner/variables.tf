variable "namespace" {
  type = string
}

variable "region" {
  type = string
}

variable "create_spanner_instance" {
  type = bool
}

variable "create_spanner_db" {
  type = bool
}

variable "spanner_instance_id" {
  type = string
}

variable "spanner_database_id" {
  type = string
}

variable "spanner_processing_units" {
  type = number
}

variable "deletion_protection" {
  type = bool
}

variable "orchestrator_email" {
  type        = string
  description = "Email of the orchestrator service account"
  default     = ""
}

variable "spanner_version_retention_period" {
  type        = string
  description = "The version retention period for the Spanner database"
  default     = "6h"
}
