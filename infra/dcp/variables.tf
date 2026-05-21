# --- Shared Global Variables ---
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "user_project_override" {
  description = "Set to true to specify a quota / billing project with billing_project_id. Default: true."
  type        = bool
  default     = true
}

variable "billing_project_id" {
  description = "If user_project_override is set to true, will use this billing project id. Default: null (will use var.project_id as the billing project)"
  type        = string
  default     = null
}

variable "deletion_protection" {
  description = "Enable deletion protection for resources (set to true for production)"
  type        = bool
  default     = false
}

variable "make_services_public" {
  description = "Whether to allow unauthenticated invocations to the Cloud Run services in the DCP and CDC stacks"
  type        = bool
  default     = false
}

# --- Stack Toggles ---
variable "enable_dcp" {
  description = "Enable the new Data Commons Platform stack"
  type        = bool
  default     = true
}


# --- DCP Stack Variables ---
variable "platform_service_image" {
  description = "Docker image URL for the platform service component"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-platform:latest"
}

variable "platform_service_name" {
  description = "Cloud Run service name for the platform service component"
  type        = string
  default     = "dcp-svc"
}

variable "platform_service_account_name" {
  description = "Service account for the platform service component"
  type        = string
  default     = "dcp-sa"
}

variable "create_spanner_instance" {
  description = "Create a new Spanner instance"
  type        = bool
  default     = false
}

variable "create_spanner_db" {
  description = "Create a new Spanner database within the specified spanner_instance_id"
  type        = bool
  default     = true
}

variable "spanner_instance_id" {
  description = "The ID of the Spanner instance"
  type        = string
  default     = ""
}

variable "spanner_database_id" {
  description = "The ID of the Spanner database"
  type        = string
  default     = "dcp-db"
}

variable "spanner_version_retention_period" {
  description = "Spanner database version retention period (e.g., 6h)"
  type        = string
  default     = "6h"
}

variable "spanner_processing_units" {
  description = "Compute capacity for the Spanner instance in processing units (1000 = 1 node)"
  type        = number
  default     = 1000
}

variable "platform_service_cpu" {
  description = "CPU limit for the platform service container"
  type        = string
  default     = "1000m"
}

variable "platform_service_memory" {
  description = "Memory limit for the platform service container"
  type        = string
  default     = "1Gi"
}

variable "platform_service_min_instances" {
  description = "Minimum number of instances for the platform service"
  type        = number
  default     = 1
}

variable "platform_service_max_instances" {
  description = "Maximum number of instances for the platform service"
  type        = number
  default     = 10
}

variable "platform_service_concurrency" {
  description = "Maximum concurrent requests per instance for the platform service"
  type        = number
  default     = 80
}

variable "platform_service_timeout_seconds" {
  description = "Request timeout in seconds for the platform service"
  type        = number
  default     = 300
}


variable "namespace" {
  description = "Global prefix for all resources"
  type        = string
  default     = ""
}

variable "cdc_dc_api_key" {
  description = "DC API Key for CDC"
  type        = string
  default     = ""
}

variable "cdc_maps_api_key" {
  description = "Maps API Key for CDC"
  type        = string
  default     = null
}

variable "cdc_disable_google_maps" {
  description = "Disable maps in CDC"
  type        = bool
  default     = false
}

variable "cdc_google_analytics_tag_id" {
  description = "GA tag for CDC"
  type        = string
  default     = null
}

variable "cdc_gcs_data_bucket_name" {
  description = "CDC data bucket"
  type        = string
  default     = ""
}

variable "cdc_gcs_data_bucket_input_folder" {
  description = "CDC input folder"
  type        = string
  default     = "input"
}

variable "cdc_gcs_data_bucket_output_folder" {
  description = "CDC output folder"
  type        = string
  default     = "output"
}

variable "cdc_gcs_data_bucket_location" {
  description = "CDC bucket location"
  type        = string
  default     = "US"
}


variable "vpc_connector_cidr" {
  description = "CIDR range for the VPC Access Connector"
  type        = string
  default     = "10.13.0.0/28"
}

variable "datacommons_service_image" {
  description = "Docker image URL for the main Data Commons service"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-services:latest"
}

variable "datacommons_service_name" {
  description = "Cloud Run service name for the main Data Commons service"
  type        = string
  default     = "datacommons-service"
}

variable "datacommons_service_min_instances" {
  description = "Minimum number of instances for the Data Commons service"
  type        = number
  default     = 1
}

variable "datacommons_service_max_instances" {
  description = "Maximum number of instances for the Data Commons service"
  type        = number
  default     = 3
}

variable "datacommons_service_cpu" {
  description = "CPU limit for the Data Commons service container"
  type        = string
  default     = "4"
}

variable "datacommons_service_memory" {
  description = "Memory limit for the Data Commons service container"
  type        = string
  default     = "16G"
}


variable "cdc_data_job_image" {
  description = "CDC data job image"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-data:latest"
}

variable "cdc_data_job_cpu" {
  description = "CDC data job CPU"
  type        = string
  default     = "8"
}

variable "cdc_data_job_memory" {
  description = "CDC data job RAM"
  type        = string
  default     = "32G"
}

variable "cdc_data_job_timeout" {
  description = "CDC data job timeout"
  type        = string
  default     = "21600s"
}

variable "cdc_search_scope" {
  description = "CDC search scope"
  type        = string
  default     = "base_and_custom"
}

variable "enable_bq_federation" {
  description = "Enable BigQuery federation to allow querying Spanner data via BigQuery"
  type        = bool
  default     = false
}

variable "bq_connection_name" {
  description = "The name of the BigQuery external connection to Spanner"
  type        = string
  default     = "spanner_connection"
}

variable "create_bq_reservation" {
  description = "Create a dedicated BigQuery reservation for federation queries"
  type        = bool
  default     = true
}

variable "bq_reservation_slot_capacity" {
  description = "Baseline compute slots for the BigQuery reservation"
  type        = number
  default     = 0
}

variable "bq_reservation_max_slots" {
  description = "Maximum slots for BigQuery reservation autoscaling"
  type        = number
  default     = 400
}

variable "cdc_enable_mcp" {
  description = "CDC enable MCP"
  type        = bool
  default     = true
}

variable "vpc_network_name" {
  description = "VPC network name"
  type        = string
  default     = "default"
}


variable "enable_redis" {
  description = "Enable a Memorystore Redis instance for caching"
  type        = bool
  default     = false
}

variable "redis_instance_name" {
  description = "The name of the Redis instance"
  type        = string
  default     = "dcp-redis-instance"
}

variable "redis_memory_size_gb" {
  description = "The memory capacity of the Redis instance in GB"
  type        = number
  default     = 2
}

variable "redis_tier" {
  description = "The service tier of the Redis instance (BASIC or STANDARD_HA)"
  type        = string
  default     = "STANDARD_HA"
}

variable "redis_location_id" {
  description = "The primary zone where the Redis instance will be located"
  type        = string
  default     = "us-central1-a"
}

variable "redis_alternative_location_id" {
  description = "The alternative zone for the failover Redis instance (required for STANDARD_HA tier)"
  type        = string
  default     = "us-central1-b"
}

variable "redis_replica_count" {
  description = "The number of read replicas for the Redis instance"
  type        = number
  default     = 1
}

# --- Ingestion Pipeline Config ---
variable "dcp_deploy_data_ingestion_workflow" {
  description = "Deploy the complete end-to-end Data Commons Ingestion workflow stack"
  type        = bool
  default     = true
}

variable "dcp_create_ingestion_bucket" {
  description = "Create a dedicated ingestion bucket for the DCP ingestion workflow"
  type        = bool
  default     = true
}

variable "dcp_external_ingestion_bucket_name" {
  description = "Existing external bucket name to use when dcp_create_ingestion_bucket is false"
  type        = string
  default     = ""
}

variable "dcp_ingestion_lock_timeout" {
  description = "Timeout for the ingestion lock in seconds"
  type        = number
  default     = 82800
}

variable "dcp_ingestion_helper_image" {
  description = "Docker image URL for the DCP ingestion helper service"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-ingestion-helper:latest"
}

