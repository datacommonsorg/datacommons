variable "project_id" {
  type        = string
  description = "GCP Project ID"
}

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

variable "enable_bq_federation" {
  type        = bool
  description = "Enable BigQuery federation to Spanner"
  default     = false
}

variable "bq_connection_name" {
  type        = string
  description = "Name of the BigQuery connection"
  default     = "spanner_connection"
}

variable "ingestion_helper_sa_email" {
  type        = string
  description = "Email of the ingestion helper service account"
  default     = ""
}

variable "spanner_version_retention_period" {
  type        = string
  description = "The version retention period for the Spanner database"
  default     = "6h"
}

variable "create_bq_reservation" {
  type        = bool
  description = "Create a new BigQuery reservation for federation queries"
  default     = true
}

variable "bq_reservation_slot_capacity" {
  type        = number
  description = "Baseline slots for BigQuery reservation"
  default     = 100
}

variable "bq_reservation_max_slots" {
  type        = number
  description = "Max slots for BigQuery reservation autoscale"
  default     = 400
}
