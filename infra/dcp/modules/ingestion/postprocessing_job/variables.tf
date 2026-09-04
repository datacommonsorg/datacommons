variable "project_id" { type = string }
variable "instance_name" { type = string }
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
variable "vpc_access" {
  type = object({
    network_id      = string
    subnet_id       = string
    vpc_egress_mode = optional(string, "PRIVATE_RANGES_ONLY")
  })
  description = "Direct VPC Egress configuration. If null, job runs without VPC egress."
  default     = null
}
variable "spanner_instance_id" { type = string }
variable "spanner_database_id" { type = string }
variable "bigquery_connection_id" { type = string }
variable "use_spanner" { type = bool }
variable "enable_bigquery_postprocessing" { type = bool }
variable "enable_spanner_embeddings" { type = bool }
variable "enable_bigquery_connection" {
  description = "Enable BigQuery connection for post-processing. Requires Spanner module to be enabled with BigQuery connection support (spanner_config.enable = true and spanner_config.enable_bigquery_connection = true)."
  type        = bool
  default     = false
}


variable "env_vars" {
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}
