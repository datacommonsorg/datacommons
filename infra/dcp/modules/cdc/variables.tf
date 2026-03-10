variable "project_id" {
  description = "The GCP project ID where the solution will be deployed"
  type        = string
}

variable "namespace" {
  description = "Prefix to apply to resource names for namespacing in a shared GCP account"
  type        = string
}

variable "dc_api_key" {
  description = "Data Commons API Key"
  type        = string
}

variable "maps_api_key" {
  description = "Google Maps API Key"
  type        = string
  default     = null
}

variable "disable_google_maps" {
  description = "Whether to show Google Maps component on the website"
  type        = bool
  default     = false
}

variable "region" {
  description = "The GCP region where project resources will be created"
  type        = string
  default     = "us-central1"
}

variable "google_analytics_tag_id" {
  description = "Google Analytics Tag ID"
  type        = string
  default     = null
}

variable "gcs_data_bucket_name" {
  description = "Custom GCS data bucket name."
  type        = string
  default     = ""
}

variable "gcs_data_bucket_input_folder" {
  description = "Input data folder in the GCS data bucket"
  type        = string
  default     = "input"
}

variable "gcs_data_bucket_output_folder" {
  description = "Output data folder in the GCS data bucket"
  type        = string
  default     = "output"
}

variable "gcs_data_bucket_location" {
  description = "Data Commons GCS data bucket location"
  type        = string
  default     = "US"
}

variable "mysql_instance_name" {
  description = "The name of the MySQL instance"
  type        = string
  default     = "datacommons-mysql-instance"
}

variable "mysql_database_name" {
  description = "MySQL database name"
  type        = string
  default     = "datacommons"
}

variable "mysql_database_version" {
  description = "The version of MySQL"
  type        = string
  default     = "MYSQL_8_0"
}

variable "mysql_cpu_count" {
  description = "Number of CPUs for the MySQL instance"
  type        = number
  default     = 2
}

variable "mysql_memory_size_mb" {
  description = "Memory size for the MySQL instance in MB"
  type        = number
  default     = 7680
}

variable "mysql_storage_size_gb" {
  description = "SSD storage size for the MySQL instance in GB"
  type        = number
  default     = 20
}

variable "mysql_user" {
  description = "The username for the MySQL instance"
  type        = string
  default     = "datacommons"
}

variable "mysql_deletion_protection" {
  description = "Mysql deletion protection"
  type        = bool
  default     = false
}

variable "dc_web_service_image" {
  description = "Container image for Cloud Run service"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-services:stable"
}

variable "dc_web_service_min_instance_count" {
  description = "Minimum number of instances for the Data Commons service"
  type        = number
  default     = 1
}

variable "dc_web_service_max_instance_count" {
  description = "Maximum number of instances for the Data Commons service"
  type        = number
  default     = 1
}

variable "dc_web_service_cpu" {
  description = "CPU limit for the Data Commons service container"
  type        = string
  default     = "4"
}

variable "dc_web_service_memory" {
  description = "Memory limit for the Data Commons service container"
  type        = string
  default     = "16G"
}

variable "make_dc_web_service_public" {
  description = "Whether to make the Data Commons Cloud Run service publicly accessible"
  type        = bool
  default     = true
}

variable "dc_data_job_image" {
  description = "The container image for the data job"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-data:stable"
}

variable "dc_data_job_cpu" {
  description = "CPU limit for the Data Commons data loading job"
  type        = string
  default     = "2"
}

variable "dc_data_job_memory" {
  description = "Memory limit for the Data Commons data loading job"
  type        = string
  default     = "8G"
}

variable "dc_data_job_timeout" {
  description = "Timeout for the Data Commons data loading job"
  type        = string
  default     = "600s"
}

variable "dc_search_scope" {
  description = "Scope for MCP search indicators"
  type        = string
  default     = "base_and_custom"
}

variable "enable_mcp" {
  description = "Whether to run the MCP server"
  type        = bool
  default     = true
}

variable "vpc_network_name" {
  description = "VPC network name to use"
  type        = string
  default     = "default"
}

variable "vpc_network_subnet_name" {
  description = "VPC network subnet name to use"
  type        = string
  default     = "default"
}

variable "enable_redis" {
  description = "Enable redis instance in this deployment"
  type        = bool
  default     = false
}

variable "redis_instance_name" {
  description = "Name of the redis instance"
  type        = string
  default     = "datacommons-redis-instance"
}

variable "redis_memory_size_gb" {
  description = "The memory size for the Redis instance in GB"
  type        = number
  default     = 2
}

variable "redis_tier" {
  description = "The service tier for the Redis instance"
  type        = string
  default     = "STANDARD_HA"
}

variable "redis_location_id" {
  description = "Redis location id (zone)"
  type        = string
  default     = "us-central1-a"
}

variable "redis_alternative_location_id" {
  description = "Redis alternate location id (alternate zone)"
  type        = string
  default     = "us-central1-b"
}

variable "redis_replica_count" {
  description = "Redis reserved IP range"
  type        = number
  default     = 1
}

variable "vpc_connector_cidr" {
  description = "CIDR range for the VPC Access Connector"
  type        = string
  default     = "10.8.0.0/28"
}

variable "deletion_protection" {
  description = "Enable deletion protection for resources"
  type        = bool
  default     = false
}

variable "use_spanner" {
  description = "Whether to use Spanner instead of Cloud SQL"
  type        = bool
  default     = false
}

variable "spanner_instance_id" {
  description = "The Spanner instance ID to use if use_spanner is true"
  type        = string
  default     = ""
}

variable "spanner_database_id" {
  description = "The Spanner database ID to use if use_spanner is true"
  type        = string
  default     = ""
}
