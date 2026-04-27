variable "shared" {
  type = object({
    project_id           = string
    region               = string
    namespace            = string
    deletion_protection  = bool
    make_services_public = bool
  })
}

variable "toggles" {
  type = object({
    enable_dcp = bool
    enable_cdc = bool
  })
}

variable "dcp" {
  type = object({
    image_url                       = string
    service_name                    = string
    service_account_name            = string
    create_spanner_instance         = bool
    create_spanner_db               = bool
    spanner_instance_id             = string
    spanner_database_id             = string
    spanner_processing_units        = number
    service_cpu                     = string
    service_memory                  = string
    service_min_instances           = number
    service_max_instances           = number
    service_concurrency             = number
    service_timeout_seconds         = number
    deploy_data_ingestion_workflow = bool
    create_ingestion_bucket         = bool
    external_ingestion_bucket_name  = string
    ingestion_lock_timeout          = number
  })
}

variable "cdc" {
  type = object({
    dc_api_key                     = string
    maps_api_key                   = string
    disable_google_maps            = bool
    google_analytics_tag_id        = string
    gcs_data_bucket_name           = string
    gcs_data_bucket_input_folder   = string
    gcs_data_bucket_output_folder  = string
    gcs_data_bucket_location       = string
    mysql_instance_name            = string
    mysql_database_name            = string
    mysql_database_version         = string
    mysql_cpu_count                = number
    mysql_memory_size_mb           = number
    mysql_user                     = string
    vpc_connector_cidr             = string
    vpc_network_name               = string
    web_service_image              = string
    web_service_min_instance_count = number
    web_service_max_instance_count = number
    web_service_cpu                = string
    web_service_memory             = string
    data_job_image                 = string
    data_job_cpu                   = string
    data_job_memory                = string
    data_job_timeout               = string
    enable_redis                   = bool
    redis_instance_name            = string
    redis_memory_size_gb           = number
    redis_tier                     = string
    redis_location_id              = string
    redis_alternative_location_id  = string
    redis_replica_count            = number
    search_scope                   = string
    enable_mcp                     = bool
  })
}
