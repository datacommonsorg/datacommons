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
variable "spanner_config" {
  type = object({
    instance_id            = string
    database_id            = string
    bigquery_connection_id = optional(string, "")
  })
  description = "Spanner database and BigQuery federation connection coordinates"
}
variable "enable_bigquery_postprocessing" { type = bool }
variable "enable_spanner_embeddings" { type = bool }



variable "env_vars" {
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}
