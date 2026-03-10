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

variable "deletion_protection" {
  description = "Enable deletion protection for resources (set to true for production)"
  type        = bool
  default     = false
}

# --- Stack Toggles ---
variable "enable_dcp" {
  description = "Enable the new Data Commons Platform stack"
  type        = bool
  default     = false
}

variable "enable_cdc" {
  description = "Enable the legacy Custom Data Commons stack"
  type        = bool
  default     = true
}

# --- DCP Stack Variables ---
variable "dcp_image_url" {
  description = "Docker image URL for DCP"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-platform:latest"
}

variable "dcp_service_name" {
  description = "Cloud Run service name for DCP"
  type        = string
  default     = "datacommons-platform"
}

variable "dcp_service_account_name" {
  description = "Service account for DCP"
  type        = string
  default     = "dcp-runner-sa"
}

variable "dcp_create_spanner" {
  description = "Create Spanner for DCP"
  type        = bool
  default     = false
}

variable "dcp_spanner_instance_id" {
  description = "Spanner instance for DCP"
  type        = string
  default     = "dcp-spanner-instance"
}

variable "dcp_spanner_database_id" {
  description = "Spanner database for DCP"
  type        = string
  default     = "dcp-spanner-db"
}

variable "dcp_spanner_processing_units" {
  description = "Spanner units for DCP"
  type        = number
  default     = 100
}

variable "dcp_cpu" {
  description = "DCP CPU"
  type        = string
  default     = "1000m"
}

variable "dcp_memory" {
  description = "DCP Memory"
  type        = string
  default     = "512Mi"
}

variable "dcp_min_instances" {
  description = "DCP min instances"
  type        = number
  default     = 0
}

variable "dcp_max_instances" {
  description = "DCP max instances"
  type        = number
  default     = 10
}

variable "dcp_concurrency" {
  description = "DCP concurrency"
  type        = number
  default     = 80
}

variable "dcp_timeout_seconds" {
  description = "DCP timeout"
  type        = number
  default     = 300
}

# --- CDC Stack Variables (Legacy) ---
variable "cdc_namespace" {
  description = "Prefix for CDC resources"
  type        = string
  default     = "cdc"
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

variable "cdc_mysql_instance_name" {
  description = "CDC MySQL name"
  type        = string
  default     = "datacommons-mysql-instance"
}

variable "cdc_mysql_database_name" {
  description = "CDC MySQL DB name"
  type        = string
  default     = "datacommons"
}

variable "cdc_mysql_database_version" {
  description = "CDC MySQL version"
  type        = string
  default     = "MYSQL_8_0"
}

variable "cdc_mysql_cpu_count" {
  description = "CDC MySQL CPU"
  type        = number
  default     = 2
}

variable "cdc_mysql_memory_size_mb" {
  description = "CDC MySQL RAM"
  type        = number
  default     = 7680
}

variable "cdc_mysql_storage_size_gb" {
  description = "CDC MySQL Disk"
  type        = number
  default     = 20
}

variable "cdc_mysql_user" {
  description = "CDC MySQL user"
  type        = string
  default     = "datacommons"
}

variable "cdc_vpc_connector_cidr" {
  description = "CIDR range for the CDC VPC Access Connector"
  type        = string
  default     = "10.13.0.0/28"
}

variable "cdc_web_service_image" {
  description = "CDC web image"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-services:stable"
}

variable "cdc_web_service_min_instance_count" {
  description = "CDC min instances"
  type        = number
  default     = 1
}

variable "cdc_web_service_max_instance_count" {
  description = "CDC max instances"
  type        = number
  default     = 1
}

variable "cdc_web_service_cpu" {
  description = "CDC web CPU"
  type        = string
  default     = "4"
}

variable "cdc_web_service_memory" {
  description = "CDC web RAM"
  type        = string
  default     = "16G"
}

variable "cdc_make_dc_web_service_public" {
  description = "CDC public access"
  type        = bool
  default     = true
}

variable "cdc_data_job_image" {
  description = "CDC data job image"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-data:stable"
}

variable "cdc_data_job_cpu" {
  description = "CDC data job CPU"
  type        = string
  default     = "2"
}

variable "cdc_data_job_memory" {
  description = "CDC data job RAM"
  type        = string
  default     = "8G"
}

variable "cdc_data_job_timeout" {
  description = "CDC data job timeout"
  type        = string
  default     = "600s"
}

variable "cdc_search_scope" {
  description = "CDC search scope"
  type        = string
  default     = "base_and_custom"
}

variable "cdc_enable_mcp" {
  description = "CDC enable MCP"
  type        = bool
  default     = true
}

variable "cdc_vpc_network_name" {
  description = "CDC VPC network"
  type        = string
  default     = "default"
}

variable "cdc_vpc_network_subnet_name" {
  description = "CDC VPC subnet"
  type        = string
  default     = "default"
}

variable "cdc_enable_redis" {
  description = "CDC enable redis"
  type        = bool
  default     = false
}

variable "cdc_redis_instance_name" {
  description = "CDC redis name"
  type        = string
  default     = "datacommons-redis-instance"
}

variable "cdc_redis_memory_size_gb" {
  description = "CDC redis size"
  type        = number
  default     = 2
}

variable "cdc_redis_tier" {
  description = "CDC redis tier"
  type        = string
  default     = "STANDARD_HA"
}

variable "cdc_redis_location_id" {
  description = "CDC redis zone"
  type        = string
  default     = "us-central1-a"
}

variable "cdc_redis_alternative_location_id" {
  description = "CDC redis alt zone"
  type        = string
  default     = "us-central1-b"
}

variable "cdc_redis_replica_count" {
  description = "CDC redis replicas"
  type        = number
  default     = 1
}
