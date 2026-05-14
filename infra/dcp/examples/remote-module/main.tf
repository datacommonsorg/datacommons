terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.11.0"
    }
  }
}

module "datacommons_dcp" {
  # Pin this to a tag/commit for reproducible deployments.
  source = "git::https://github.com/datacommonsorg/datacommons.git//infra/dcp?ref=main"

  project_id = var.project_id
  namespace  = var.namespace
  cdc_dc_api_key = var.dc_api_key

  enable_dcp = true
  enable_cdc = true

  dcp_create_spanner_instance        = var.dcp_create_spanner_instance
  dcp_spanner_instance_id            = var.dcp_spanner_instance_id
  dcp_spanner_database_id            = var.dcp_spanner_database_id
  dcp_deploy_data_ingestion_workflow = var.dcp_deploy_data_ingestion_workflow
  dcp_ingestion_helper_image         = var.dcp_ingestion_helper_image
  cdc_gcs_data_bucket_input_folder   = var.gcs_data_bucket_input_folder
  cdc_data_job_image                 = var.cdc_data_job_image
}

variable "project_id" {
  description = "GCP project id"
  type        = string
}

variable "namespace" {
  description = "Prefix applied to provisioned resource names"
  type        = string
}

variable "dc_api_key" {
  description = "Data Commons API key"
  type        = string
  default     = ""
  sensitive = true
}

variable "dcp_create_spanner_instance" {
  description = "Create a new Spanner instance for DCP"
  type        = bool
  default     = true
}

variable "dcp_spanner_instance_id" {
  description = "Spanner instance id for DCP"
  type        = string
  default     = ""
}

variable "dcp_spanner_database_id" {
  description = "Spanner database id for DCP"
  type        = string
  default     = "dcp-db"
}

variable "dcp_deploy_data_ingestion_workflow" {
  description = "Deploy the complete end-to-end Data Commons Ingestion workflow stack"
  type        = bool
  default     = true
}

variable "dcp_ingestion_helper_image" {
  description = "Docker image URL for the DCP ingestion helper service"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-ingestion-helper:latest"
}

variable "gcs_data_bucket_input_folder" {
  description = "GCS data bucket input folder for CDC"
  type        = string
  default     = "input"
}

variable "cdc_data_job_image" {
  description = "Docker image URL for the CDC data ingestion job"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-data:stable"
}

output "dcp_service_url" {
  value = module.datacommons_dcp.dcp_service_url
}

output "dcp_spanner_instance_id" {
  value = module.datacommons_dcp.dcp_spanner_instance_id
}

output "dcp_spanner_database_id" {
  value = module.datacommons_dcp.dcp_spanner_database_id
}

output "dcp_ingestion_helper_uri" {
  value = module.datacommons_dcp.dcp_ingestion_helper_uri
}

output "cdc_service_url" {
  value = module.datacommons_dcp.cdc_service_url
}

output "cdc_data_job_name" {
  value = module.datacommons_dcp.cdc_data_job_name
}

output "workflow_name" {
  value = module.datacommons_dcp.workflow_name
}
