variable "global" {
  type = object({
    project_id                  = string
    region                      = string
    namespace                   = string
    deletion_protection         = bool
    allow_unauthenticated_access = bool
  })
}

variable "spanner_config" {
  type = object({
    create_instance            = bool
    create_db                  = bool
    instance_id                = string
    database_id                = string
    version_retention_period   = string
    processing_units          = number
  })
}

variable "bq_federation_config" {
  type = object({
    enable            = bool
    connection_name   = string
    create_reservation = bool
    slot_capacity     = number
    max_slots         = number
  })
}

variable "datacommons_service_config" {
  type = object({
    enable               = bool
    image                = string
    name                 = string
    min_instances        = number
    max_instances        = number
    cpu                  = string
    memory               = string
    dc_api_key           = string
    maps_api_key         = string
    enable_google_maps   = bool
    google_analytics_tag = string
    enable_mcp           = bool
    search_scope         = string
    instructions_dir     = string
  })
}

variable "platform_service_config" {
  type = object({
    enable          = bool
    image           = string
    name            = string
    account_name    = string
    cpu             = string
    memory          = string
    min_instances   = number
    max_instances   = number
    concurrency     = number
    timeout_seconds = number
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
    prep_job_image  = string
    prep_job_cpu    = string
    prep_job_memory = string
    prep_job_timeout = string
    prep_bucket_name = string
    prep_bucket_input_folder = string
    prep_bucket_output_folder = string
    prep_bucket_location = string
    create_prep_bucket   = bool
    
    deploy_workflow  = bool
    lock_timeout     = number
    helper_image     = string
    create_bucket    = bool
    bucket_name      = string
  })
}
