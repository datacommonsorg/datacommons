# =============================================================================
# Global Configuration
# =============================================================================

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "The default GCP region where regional resources (such as Cloud Run services, Spanner databases, and storage buckets) will be provisioned."
  type        = string
  default     = "us-central1"
}

variable "namespace" {
  description = "A unique identifier used as a prefix for resource naming. This prevents naming conflicts when deploying multiple isolated environments (like dev, staging, or feature branches) within the same GCP project."
  type        = string
  default     = ""
}

variable "stateful_deletion_protection" {
  description = "Enable deletion protection for stateful resources (Spanner, GCS) to prevent data loss."
  type        = bool
  default     = false
}

variable "stateless_deletion_protection" {
  description = "Enable deletion protection for stateless resources (Cloud Run, Workflows)."
  type        = bool
  default     = false
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

variable "dcp_version" {
  description = "The version of the Data Commons Platform to deploy. This controls the default tag for Docker images and template paths if specific overrides are not provided."
  type        = string
  default     = "1.1.0"
}

# =============================================================================
# Auth Module
# =============================================================================

variable "auth_google_datacommons_api_key" {
  description = "API key used to authenticate and connect to the remote Base Data Commons instance"
  type        = string
  default     = ""
}

variable "auth_google_maps_api_key" {
  description = "Optional Google Maps API key. If provided, it will be used and Terraform will NOT create a new key (and will destroy any auto-generated key it was previously managing)."
  type        = string
  default     = null
}

variable "auth_create_google_maps_api_key" {
  description = "Whether to automatically create a restricted Google Maps API key. This only applies if auth_google_maps_api_key is not provided (null)."
  type        = bool
  default     = true
}

# =============================================================================
# Storage Module
# =============================================================================

variable "storage_create_artifacts_bucket" {
  description = "Create a dedicated GCS bucket for Data Commons artifacts"
  type        = bool
  default     = true
}

variable "storage_artifacts_bucket_name" {
  description = "The name of the unified GCS bucket for artifacts (serving and ingestion). If not provided, a name will be automatically generated following the pattern [namespace-]dc-artifacts-[project_id]"
  type        = string
  default     = ""
}

# =============================================================================
# Redis Module
# =============================================================================

variable "enable_redis" {
  description = "Enable a Memorystore Redis instance for caching"
  type        = bool
  default     = false
}

variable "redis_instance_name" {
  description = "The name of the Redis instance. If not provided, a name will be automatically generated following the pattern [namespace-]dc-redis-instance"
  type        = string
  default     = ""
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

variable "redis_vpc_network_name" {
  description = "VPC network name"
  type        = string
  default     = "default"
}

variable "redis_vpc_connector_cidr" {
  description = "CIDR range for the VPC Access Connector"
  type        = string
  default     = "10.13.0.0/28"
}

# =============================================================================
# Spanner Module
# =============================================================================

variable "enable_spanner" {
  description = "Enable Cloud Spanner database"
  type        = bool
  default     = true
}

variable "spanner_create_instance" {
  description = "Create a new Spanner instance"
  type        = bool
  default     = false
}

variable "spanner_create_database" {
  description = "Create a new Spanner database within the specified spanner_instance_id"
  type        = bool
  default     = true
}

variable "spanner_instance_id" {
  description = "The ID of the Spanner instance. If not provided, a name will be automatically generated following the pattern [namespace-]dc-instance"
  type        = string
  default     = ""
}

variable "spanner_database_id" {
  description = "The ID of the Spanner database. If not provided, a name will be automatically generated following the pattern [namespace-]dc-db"
  type        = string
  default     = ""
}

variable "spanner_version_retention_period" {
  description = "Spanner database version retention period (e.g., 6h)"
  type        = string
  default     = "6h"
}

variable "spanner_processing_units" {
  description = "Compute capacity for the Spanner instance in processing units (1000 = 1 node). Defaults to 100 if not specified."
  type        = number
  default     = null
}

variable "spanner_enable_bigquery_connection" {
  description = "Enable BigQuery connection to allow querying Spanner data via BigQuery."
  type        = bool
  default     = true
}

variable "spanner_enable_embeddings_generation" {
  description = "Enable embedding generation in Spanner"
  type        = bool
  default     = true
}

variable "spanner_bigquery_connection_name" {
  description = "The name of the BigQuery external connection to Spanner"
  type        = string
  default     = "spanner_connection"
}

variable "spanner_create_bigquery_reservation" {
  description = "Create a dedicated BigQuery reservation for federation queries"
  type        = bool
  default     = false
}

variable "spanner_bigquery_reservation_slot_capacity" {
  description = "Baseline compute slots for the BigQuery reservation"
  type        = number
  default     = 0
}

variable "spanner_bigquery_reservation_max_slots" {
  description = "Maximum slots for BigQuery reservation autoscaling"
  type        = number
  default     = 400
}

# =============================================================================
# Datacommons Services Module
# =============================================================================

variable "enable_datacommons_services" {
  description = "Enable the main Data Commons services"
  type        = bool
  default     = true
}

variable "datacommons_services_image" {
  description = "Docker image URL for the main Data Commons services. If not provided (null), defaults to the stable image defined in the services module (modules/datacommons_services/variables.tf)."
  type        = string
  default     = null
}

variable "datacommons_services_name" {
  description = "Cloud Run service name for the main Data Commons services"
  type        = string
  default     = "datacommons-service"
}

variable "datacommons_services_min_instances" {
  description = "Minimum number of instances for the Data Commons services"
  type        = number
  default     = 1
}

variable "datacommons_services_max_instances" {
  description = "Maximum number of instances for the Data Commons services"
  type        = number
  default     = 3
}

variable "datacommons_services_cpu" {
  description = "CPU limit for the Data Commons services container"
  type        = string
  default     = "4"
}

variable "datacommons_services_memory" {
  description = "Memory limit for the Data Commons services container"
  type        = string
  default     = "16G"
}

variable "datacommons_services_allow_unauthenticated_access" {
  description = "Allow unauthenticated access to the public-facing services of the Data Commons Platform"
  type        = bool
  default     = false
}

variable "datacommons_services_google_analytics_tag_id" {
  description = "Google Analytics tag ID for frontend usage tracking (only relevant if the website is deployed)"
  type        = string
  default     = null
}

variable "datacommons_services_website_disable_google_maps_api" {
  description = "Disable Google Maps integration for the website"
  type        = bool
  default     = false
}

variable "datacommons_services_enable_mcp" {
  description = "Enable Model Context Protocol (MCP) support"
  type        = bool
  default     = true
}

variable "datacommons_services_mcp_search_scope" {
  description = "Controls the datasets (base and/or custom) that are searched in response to AI queries"
  type        = string
  default     = "base_and_custom"
}

variable "datacommons_services_mcp_instructions_path" {
  description = "Directory path for customized instructions for server tools and agents"
  type        = string
  default     = null
}

# TODO(shixiao): Remove this variable to only resolve on spanner embeddings
variable "datacommons_services_resolve_with_spanner_embeddings" {
  description = "Enable resolving search queries with Spanner embeddings. Requires Spanner to be enabled (enable_spanner = true)."
  type        = bool
  default     = true
}

# =============================================================================
# Ingestion - Preprocessing Job
# =============================================================================

variable "ingestion_preprocessing_job_image" {
  description = "Docker image URL for the data ingestion pre-processing job. If not provided (null), defaults to the stable image defined in the preprocessing module (modules/ingestion/preprocessing_job/variables.tf)."
  type        = string
  default     = null
}

variable "ingestion_preprocessing_job_cpu" {
  description = "CPU limit for the pre-processing job container"
  type        = string
  default     = "8"
}

variable "ingestion_preprocessing_job_memory" {
  description = "Memory limit for the pre-processing job container"
  type        = string
  default     = "32G"
}

variable "ingestion_preprocessing_job_timeout" {
  description = "Request timeout for the pre-processing job"
  type        = string
  default     = "21600s"
}

# =============================================================================
# Ingestion - Postprocessing Job
# =============================================================================

variable "ingestion_postprocessing_job_image" {
  description = "Docker image URL for the data ingestion post-processing aggregation job. If not provided (null), defaults to the stable image tagged with dcp_version."
  type        = string
  default     = null
}

variable "ingestion_postprocessing_job_cpu" {
  description = "CPU limit for the post-processing job container"
  type        = string
  default     = "2"
}

variable "ingestion_postprocessing_job_memory" {
  description = "Memory limit for the post-processing job container"
  type        = string
  default     = "8Gi"
}

variable "ingestion_postprocessing_job_timeout" {
  description = "Execution timeout for the post-processing job"
  type        = string
  default     = "21600s"
}

variable "ingestion_input_path" {
  description = "Path within the bucket where raw files are uploaded"
  type        = string
  default     = "ingestion/input"
}

# =============================================================================
# Ingestion - Workflow
# =============================================================================

variable "enable_ingestion" {
  description = "Enable the complete end-to-end Data Commons Ingestion workflow stack"
  type        = bool
  default     = true
}

variable "ingestion_workflow_lock_acquisition_timeout" {
  description = "Timeout for the ingestion lock in seconds"
  type        = number
  default     = 82800
}

variable "ingestion_workflow_enable_bigquery_postprocessing" {
  description = "Enable BigQuery post-processing (aggregation) in the ingestion workflow"
  type        = bool
  default     = true
}

variable "ingestion_artifacts_path" {
  description = "Path where pre-processed files are placed for the next stage"
  type        = string
  default     = "ingestion/internal"
}

# =============================================================================
# Ingestion - Helper Service
# =============================================================================

variable "ingestion_helper_service_image" {
  description = "Docker image URL for the ingestion support service. If not provided (null), defaults to the stable image defined in the helper service module (modules/ingestion/helper_service/variables.tf)."
  type        = string
  default     = null
}

# =============================================================================
# Ingestion - Dataflow Network Configuration
# =============================================================================

variable "ingestion_dataflow_ip_configuration" {
  description = "IP configuration for Dataflow workers (WORKER_IP_UNSPECIFIED, WORKER_IP_PUBLIC, WORKER_IP_PRIVATE). Set to WORKER_IP_PRIVATE when a compute.vmExternalIpAccess org policy restricts VMs from obtaining external IPs."
  type        = string
  default     = "WORKER_IP_UNSPECIFIED"
}

variable "ingestion_dataflow_subnetwork" {
  description = "Subnetwork for Dataflow workers. Required when ingestion_dataflow_ip_configuration is WORKER_IP_PRIVATE. Format: regions/{region}/subnetworks/{subnetwork}."
  type        = string
  default     = ""
}

# =============================================================================
# Ingestion - Dataflow Template Configuration
# =============================================================================

variable "ingestion_dataflow_template_gcs_path" {
  description = "GCS path to the Dataflow Flex Template container spec. If not provided (null), defaults to the stable template defined in the workflow module (modules/ingestion/workflow/variables.tf)."
  type        = string
  default     = null
}

