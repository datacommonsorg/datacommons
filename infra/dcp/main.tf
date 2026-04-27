terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.11.0"
    }
    null = {
      source  = "hashicorp/null"
      version = ">= 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0"
    }
  }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = var.user_project_override
  billing_project       = var.billing_project_id != null ? var.billing_project_id : var.project_id
}

provider "google-beta" {
  project               = var.project_id
  region                = var.region
  user_project_override = var.user_project_override
  billing_project       = var.billing_project_id != null ? var.billing_project_id : var.project_id
}

resource "google_project_service" "apis" {
  for_each = toset(concat([
    "apikeys.googleapis.com",
    "run.googleapis.com",
    "iam.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "secretmanager.googleapis.com",
    "vpcaccess.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com"
    ], var.enable_dcp ? ["spanner.googleapis.com"] : [], var.dcp_deploy_data_ingestion_workflow ? [
    "workflows.googleapis.com",
    "workflowexecutions.googleapis.com",
    "dataflow.googleapis.com"
  ] : []))

  service            = each.key
  disable_on_destroy = false
}

locals {
  stack_shared = {
    project_id           = var.project_id
    region               = var.region
    namespace            = var.namespace
    deletion_protection  = var.deletion_protection
    make_services_public = var.make_services_public
  }

  stack_toggles = {
    enable_dcp = var.enable_dcp
    enable_cdc = var.enable_cdc
  }

  stack_dcp = {
    image_url                      = var.dcp_image_url
    service_name                   = var.dcp_service_name
    service_account_name           = var.dcp_service_account_name
    create_spanner_instance        = var.dcp_create_spanner_instance
    create_spanner_db              = var.dcp_create_spanner_db
    spanner_instance_id            = var.dcp_spanner_instance_id
    spanner_database_id            = var.dcp_spanner_database_id
    spanner_processing_units       = var.dcp_spanner_processing_units
    service_cpu                    = var.dcp_service_cpu
    service_memory                 = var.dcp_service_memory
    service_min_instances          = var.dcp_service_min_instances
    service_max_instances          = var.dcp_service_max_instances
    service_concurrency            = var.dcp_service_concurrency
    service_timeout_seconds        = var.dcp_service_timeout_seconds
    deploy_data_ingestion_workflow = var.dcp_deploy_data_ingestion_workflow
    create_ingestion_bucket        = var.dcp_create_ingestion_bucket
    external_ingestion_bucket_name = var.dcp_external_ingestion_bucket_name
    ingestion_lock_timeout         = var.dcp_ingestion_lock_timeout
  }

  stack_cdc = {
    dc_api_key                     = var.cdc_dc_api_key
    maps_api_key                   = coalesce(var.cdc_maps_api_key, "")
    disable_google_maps            = var.cdc_disable_google_maps
    google_analytics_tag_id        = coalesce(var.cdc_google_analytics_tag_id, "")
    gcs_data_bucket_name           = var.cdc_gcs_data_bucket_name
    gcs_data_bucket_input_folder   = var.cdc_gcs_data_bucket_input_folder
    gcs_data_bucket_output_folder  = var.cdc_gcs_data_bucket_output_folder
    gcs_data_bucket_location       = var.cdc_gcs_data_bucket_location
    mysql_instance_name            = var.cdc_mysql_instance_name
    mysql_database_name            = var.cdc_mysql_database_name
    mysql_database_version         = var.cdc_mysql_database_version
    mysql_cpu_count                = var.cdc_mysql_cpu_count
    mysql_memory_size_mb           = var.cdc_mysql_memory_size_mb
    mysql_user                     = var.cdc_mysql_user
    vpc_connector_cidr             = var.cdc_vpc_connector_cidr
    vpc_network_name               = var.cdc_vpc_network_name
    web_service_image              = var.cdc_web_service_image
    web_service_min_instance_count = var.cdc_web_service_min_instance_count
    web_service_max_instance_count = var.cdc_web_service_max_instance_count
    web_service_cpu                = var.cdc_web_service_cpu
    web_service_memory             = var.cdc_web_service_memory
    data_job_image                 = var.cdc_data_job_image
    data_job_cpu                   = var.cdc_data_job_cpu
    data_job_memory                = var.cdc_data_job_memory
    data_job_timeout               = var.cdc_data_job_timeout
    enable_redis                   = var.cdc_enable_redis
    redis_instance_name            = var.cdc_redis_instance_name
    redis_memory_size_gb           = var.cdc_redis_memory_size_gb
    redis_tier                     = var.cdc_redis_tier
    redis_location_id              = var.cdc_redis_location_id
    redis_alternative_location_id  = var.cdc_redis_alternative_location_id
    redis_replica_count            = var.cdc_redis_replica_count
    search_scope                   = coalesce(var.cdc_search_scope, "")
    enable_mcp                     = var.cdc_enable_mcp
  }
}

module "stack" {
  source = "./modules/stack"

  shared  = local.stack_shared
  toggles = local.stack_toggles
  dcp     = local.stack_dcp
  cdc     = local.stack_cdc

  depends_on = [google_project_service.apis]
}
