variable "project_id" {
  type        = string
  description = "The GCP project ID where resources will be deployed"
}

variable "instance_name" {
  type        = string
  description = "Instance identifier used for resource naming prefix"
}

variable "region" {
  type        = string
  description = "The GCP region for the Cloud Run job and BigQuery connection"
}

variable "stateless_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for stateless resources (Cloud Run Job) to prevent accidental deletion."
}

variable "image" {
  type        = string
  nullable    = false
  description = "Docker image URL for the data ingestion post-processing aggregation job"
}

variable "cpu" {
  type        = string
  description = "CPU limit for the postprocessing job container"
}

variable "memory" {
  type        = string
  description = "Memory limit for the postprocessing job container"
}

variable "timeout" {
  type        = string
  description = "Execution timeout for the postprocessing job (e.g., '3600s')"
}

variable "vpc_access" {
  type = object({
    network_id      = string
    subnet_id       = string
    vpc_egress_mode = optional(string, "PRIVATE_RANGES_ONLY")
  })
  description = "Direct VPC Egress configuration. If null, job runs without VPC egress."
  default     = null
}

variable "spanner_config" {
  type = object({
    instance_id                = string
    database_id                = string
    enable_bigquery_connection = optional(bool, false)
    bigquery_connection_id     = optional(string, "")
  })
  description = "Spanner database and BigQuery federation connection coordinates"
}

variable "enable_bigquery_postprocessing" {
  type        = bool
  description = "Flag to enable BigQuery postprocessing aggregations and grant BigQuery IAM roles"
}

variable "enable_embeddings_generation" {
  type        = bool
  description = "Flag to enable Spanner vector embedding generation"
}
