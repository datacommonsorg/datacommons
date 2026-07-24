variable "project_id" {
  type        = string
  description = "GCP Project ID"
}

variable "instance_name" {
  type = string
}

variable "region" {
  type = string
}

variable "create_instance" {
  type = bool
}

variable "create_database" {
  type = bool
}

variable "instance_id" {
  type    = string
  default = ""
}

variable "database_id" {
  type    = string
  default = ""
}

variable "processing_units" {
  type     = number
  default  = 100
  nullable = false
}

variable "stateful_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for the Spanner database"
}


variable "enable_bigquery_connection" {
  type        = bool
  description = "Enable BigQuery federation to Spanner"
  default     = false
}

variable "bigquery_connection_name" {
  type        = string
  description = "Name of the BigQuery connection"
  default     = "spanner_connection"
}


variable "version_retention_period" {
  type        = string
  description = "The version retention period for the Spanner database"
  default     = "6h"
}

variable "create_bigquery_reservation" {
  type        = bool
  description = "Create a new BigQuery reservation for federation queries"
  default     = true
}

variable "bigquery_reservation_slot_capacity" {
  type        = number
  description = "Baseline slots for BigQuery reservation"
  default     = 0
}

variable "bigquery_reservation_max_slots" {
  type        = number
  description = "Max slots for BigQuery reservation autoscale"
  default     = 400
}
