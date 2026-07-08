variable "deploy" {
  type = bool
}

variable "namespace" {
  type = string
}

variable "region" {
  type = string
}

variable "stateless_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for stateless resources (Workflows) to prevent accidental deletion."
}

variable "project_id" {
  type = string
}

variable "lock_acquisition_timeout" {
  type = number
}

variable "ingestion_helper_url" {
  type = string
}

variable "dataflow_service_account_email" {
  type = string
}

variable "enable_bigquery_postprocessing" {
  type    = bool
  default = false
}

variable "enable_embeddings_generation" {
  type        = bool
  description = "Enable embedding generation"
}

variable "embeddings_timeout" {
  type        = number
  description = "Timeout in seconds for ingestion helper service HTTP post"
  default     = 1800
}

variable "ingestion_helper_service_name" {
  type        = string
  description = "Name of the ingestion helper Cloud Run service"
  default     = ""
}

variable "enable_redis_cache_clearing" {
  type        = bool
  description = "Flag to enable Redis cache clearing"
  default     = false
}

variable "preprocessing_job_name" {
  type        = string
  description = "Name of the ingestion preprocessing Cloud Run job"
  default     = ""
}

variable "ingestion_artifacts_path" {
  type        = string
  description = "Path where pre-processed files are placed for the next stage"
}

variable "dataflow_ip_configuration" {
  type        = string
  description = <<-EOT
    IP configuration for Dataflow workers. Set to WORKER_IP_PRIVATE for
    environments where an org policy (compute.vmExternalIpAccess) restricts
    VMs from obtaining external IPs. Requires Private Google Access and
    Cloud NAT on the target subnet.
    Valid values: WORKER_IP_UNSPECIFIED, WORKER_IP_PUBLIC, WORKER_IP_PRIVATE.
    See: https://cloud.google.com/dataflow/docs/reference/rest/v1b3/projects.locations.flexTemplates/launch#FlexTemplateRuntimeEnvironment
  EOT
  default     = "WORKER_IP_UNSPECIFIED"
  validation {
    condition     = contains(["WORKER_IP_UNSPECIFIED", "WORKER_IP_PUBLIC", "WORKER_IP_PRIVATE"], var.dataflow_ip_configuration)
    error_message = "Must be one of: WORKER_IP_UNSPECIFIED, WORKER_IP_PUBLIC, WORKER_IP_PRIVATE."
  }
}

variable "dataflow_subnetwork" {
  type        = string
  description = <<-EOT
    Subnetwork for Dataflow workers. Required when dataflow_ip_configuration
    is WORKER_IP_PRIVATE. Format: regions/{region}/subnetworks/{subnetwork}.
  EOT
  default     = ""

  validation {
    condition     = var.dataflow_subnetwork == "" || can(regex("regions/[a-zA-Z0-9-]+/subnetworks/[a-zA-Z0-9-]+$", var.dataflow_subnetwork))
    error_message = "dataflow_subnetwork must be in the format 'regions/{region}/subnetworks/{subnetwork}' or a full self-link ending with that format."
  }
}

check "dataflow_private_ip_requires_subnetwork" {
  assert {
    condition     = var.dataflow_ip_configuration != "WORKER_IP_PRIVATE" || var.dataflow_subnetwork != ""
    error_message = "dataflow_subnetwork must be specified when dataflow_ip_configuration is WORKER_IP_PRIVATE."
  }
}

variable "dataflow_template_gcs_path" {
  type        = string
  description = "GCS path to the Dataflow Flex Template container spec"
  default     = "gs://datcom-templates/templates/flex/ingestion-1.1.0.json"
  nullable    = false

  validation {
    condition     = can(regex("^gs://.+[.]json$", var.dataflow_template_gcs_path))
    error_message = "The dataflow_template_gcs_path must be a valid GCS path starting with 'gs://' and ending with '.json'."
  }
}

