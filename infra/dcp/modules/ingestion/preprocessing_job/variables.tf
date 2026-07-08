variable "project_id" { type = string }
variable "namespace" { type = string }
variable "region" { type = string }
variable "stateless_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for stateless resources (Cloud Run Job) to prevent accidental deletion."
}
variable "image" {
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-data:beep.boop.bop"
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

variable "secret_env_vars" {
  type = list(object({
    name    = string
    secret  = string
    version = string
  }))
}

variable "dc_api_key_secret_id" {
  type        = string
  description = "Secret ID for Data Commons API key"
  default     = ""
}

variable "maps_api_key_secret_id" {
  type        = string
  description = "Secret ID for Maps API key"
  default     = ""
}

variable "enable_spanner_embeddings" {
  type        = bool
  description = "Whether to enable Spanner embeddings generation (and skip GCS embeddings in preprocessing)"
  default     = true
}
