variable "deploy" {
  type = bool
}

variable "project_id" {
  type = string
}

variable "namespace" {
  type = string
}

variable "ingestion_bucket_name" {
  type = string
}

<<<<<<< Updated upstream
variable "use_spanner" {
  type    = bool
  default = true
}

=======
variable "bigquery_connection_id" {
  type        = string
  description = "Secret ID for BigQuery connection"
  default     = ""
}

variable "region" {
  type        = string
  description = "GCP region"
}
>>>>>>> Stashed changes
