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
  description = "Docker image URL for the data ingestion pre-processing job"
}
variable "cpu" { type = string }
variable "memory" { type = string }
variable "timeout" { type = string }
variable "vpc_connector_id" { type = string }
variable "bucket_name" { type = string }
variable "input_path" { type = string }
variable "ingestion_artifacts_path" { type = string }
variable "run_database_init" { type = bool }
variable "use_spanner" { type = bool }

variable "env_vars" {
  type = list(object({
    name  = string
    value = string
  }))
}

variable "env_secrets" {
  type = map(object({
    secret_id = string
    enabled   = bool
  }))
  default     = {}
  description = <<-EOT
    Map of secrets to grant access to and mount in the job, where the key is the environment variable name.
    Example:
    {
      "DC_API_KEY" = {
        secret_id = "projects/my-project/secrets/my-secret"
        enabled   = true
      }
    }
  EOT
}

variable "enable_spanner_embeddings" {
  type        = bool
  description = "Whether to enable Spanner embeddings generation (and skip GCS embeddings in preprocessing)"
  default     = true
}
