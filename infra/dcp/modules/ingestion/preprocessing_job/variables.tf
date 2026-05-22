variable "project_id" { type = string }
variable "namespace" { type = string }
variable "region" { type = string }
variable "deletion_protection" { type = bool }
variable "image" { type = string }
variable "cpu" { type = string }
variable "memory" { type = string }
variable "timeout" { type = string }
variable "service_account_email" { type = string }
variable "vpc_connector_id" { type = string }
variable "bucket_name" { type = string }
variable "input_path" { type = string }
variable "workflow_artifacts_path" { type = string }
variable "run_db_init" { type = bool }
variable "use_spanner" { type = bool }
variable "orchestrator_email" { type = string }

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
