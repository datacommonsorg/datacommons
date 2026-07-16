variable "project_id" { type = string }
variable "namespace" { type = string }
variable "region" { type = string }
variable "stateless_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for stateless resources (Cloud Run Job) to prevent accidental deletion."
}
variable "image" {
  type        = string
  nullable    = false
  description = "Docker image URL for the data ingestion post-processing aggregation job"
}
variable "cpu" { type = string }
variable "memory" { type = string }
variable "timeout" { type = string }
variable "vpc_connector_id" {
  type        = string
  nullable    = true
  default     = null
  description = "VPC Serverless Connector ID for private database access."
}
variable "spanner_instance_id" { type = string }
variable "spanner_database_id" { type = string }
variable "bigquery_connection_id" { type = string }
variable "use_spanner" { type = bool }
variable "enable_bigquery_postprocessing" { type = bool }
variable "enable_spanner_embeddings" { type = bool }

variable "env_vars" {
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}
