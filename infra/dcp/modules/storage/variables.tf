variable "enable_dcp" {
  type = bool
}

variable "enable_cdc" {
  type = bool
}

variable "project_id" {
  type = string
}

variable "namespace" {
  type = string
}

variable "dcp_deploy" {
  type = bool
}

variable "dcp_create_bucket" {
  type = bool
}

variable "dcp_external_bucket_name" {
  type = string
}

variable "dcp_region" {
  type = string
}

variable "dcp_deletion_protection" {
  type = bool
}

variable "cdc_gcs_data_bucket_name" {
  type = string
}

variable "cdc_gcs_data_bucket_location" {
  type = string
}
