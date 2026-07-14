variable "global" {
  type = object({
    project_id                    = string
    region                        = string
    namespace                     = string
    stateful_deletion_protection  = bool
    stateless_deletion_protection = bool
  })
}

variable "storage_create_artifacts_bucket" {
  type    = bool
  default = true
}

variable "storage_artifacts_bucket_name" {
  type = string
}

variable "spanner_config" {
  type = object({
    enable                             = bool
    create_instance                    = bool
    create_db                          = bool
    instance_id                        = string
    database_id                        = string
    version_retention_period           = string
    processing_units                   = number
    enable_bigquery_connection         = bool
    enable_embeddings_generation       = bool
    bigquery_connection_name           = string
    create_bigquery_reservation        = bool
    bigquery_reservation_slot_capacity = number
    bigquery_reservation_max_slots     = number
  })
}

variable "datacommons_services_config" {
  type = object({
    enable                          = bool
    image                           = optional(string)
    name                            = string
    min_instances                   = number
    max_instances                   = number
    cpu                             = string
    memory                          = string
    google_analytics_tag            = string
    enable_mcp                      = bool
    search_scope                    = string
    instructions_path               = string
    allow_unauthenticated_access    = bool
    website_disable_google_maps_api = bool
    resolve_with_spanner_embeddings = bool
  })
}

variable "auth_config" {
  type = object({
    google_datacommons_api_key = string
    google_maps_api_key        = string
    create_google_maps_key     = bool
  })
}




variable "redis_config" {
  type = object({
    enable                  = bool
    instance_name           = string
    memory_size_gb          = number
    tier                    = string
    location_id             = string
    alternative_location_id = string
    replica_count           = number
    vpc_network_name        = string
    vpc_connector_cidr      = string
  })
}

variable "ingestion_config" {
  type = object({
    # Global Toggles
    enable_ingestion                        = bool
    workflow_enable_bigquery_postprocessing = bool

    # Storage & Paths
    input_path               = string
    ingestion_artifacts_path = string

    # Preprocessing Job
    preprocessing_job_image         = optional(string)
    preprocessing_job_cpu           = string
    preprocessing_job_memory        = string
    preprocessing_job_timeout       = string
    preprocessing_job_tmp_disk_size = optional(string)

    # Workflow & Helper Service
    workflow_lock_acquisition_timeout = number
    helper_service_image              = optional(string)

    # Dataflow network configuration
    # Use WORKER_IP_PRIVATE when a compute.vmExternalIpAccess org policy
    # blocks Dataflow workers from obtaining external IPs.
    dataflow_ip_configuration  = optional(string, "WORKER_IP_UNSPECIFIED")
    dataflow_subnetwork        = optional(string, "")
    dataflow_template_gcs_path = optional(string)
  })
}
