variable "project_id" { type = string }
variable "namespace" { type = string }
variable "region" { type = string }
variable "deletion_protection" { type = bool }
variable "dc_data_job_image" { type = string }
variable "dc_data_job_cpu" { type = string }
variable "dc_data_job_memory" { type = string }
variable "dc_data_job_timeout" { type = string }
variable "service_account_email" { type = string }
variable "vpc_connector_id" { type = string }
variable "bucket_name" { type = string }
variable "gcs_data_bucket_input_folder" { type = string }
variable "gcs_data_bucket_output_folder" { type = string }
variable "run_db_init" { type = bool }

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
