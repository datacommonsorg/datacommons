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
    ], (var.enable_platform_service || var.enable_datacommons_service) ? ["spanner.googleapis.com"] : [],
    var.deploy_ingestion_workflow ? [
    "workflows.googleapis.com",
    "workflowexecutions.googleapis.com",
    "dataflow.googleapis.com"
    ] : [], var.enable_bq_federation ? [
    "bigqueryconnection.googleapis.com",
    "bigquery.googleapis.com",
    "bigqueryreservation.googleapis.com"
  ] : []))

  service            = each.key
  disable_on_destroy = false
}

locals {
  global_config = {
    project_id                  = var.project_id
    region                      = var.region
    namespace                   = var.namespace
    deletion_protection         = var.deletion_protection
    allow_unauthenticated_access = var.allow_unauthenticated_access
  }

  spanner_config = {
    create_instance            = var.create_spanner_instance
    create_db                  = var.create_spanner_db
    instance_id                = var.spanner_instance_id
    database_id                = var.spanner_database_id
    version_retention_period   = var.spanner_version_retention_period
    processing_units          = var.spanner_processing_units
  }

  bq_federation_config = {
    enable            = var.enable_bq_federation
    connection_name   = var.bq_connection_name
    create_reservation = var.create_bq_reservation
    slot_capacity     = var.bq_reservation_slot_capacity
    max_slots         = var.bq_reservation_max_slots
  }

  datacommons_service_config = {
    enable               = var.enable_datacommons_service
    image                = var.datacommons_service_image
    name                 = var.datacommons_service_name
    min_instances        = var.datacommons_service_min_instances
    max_instances        = var.datacommons_service_max_instances
    cpu                  = var.datacommons_service_cpu
    memory               = var.datacommons_service_memory
    dc_api_key           = var.base_dc_api_key
    maps_api_key         = var.maps_api_key
    enable_google_maps   = var.enable_google_maps
    google_analytics_tag = var.google_analytics_tag_id
    enable_mcp           = var.enable_mcp
    search_scope         = var.mcp_search_scope
    instructions_dir     = var.mcp_instructions_dir
  }

  platform_service_config = {
    enable          = var.enable_platform_service
    image           = var.platform_service_image
    name            = var.platform_service_name
    account_name    = var.platform_service_account_name
    cpu             = var.platform_service_cpu
    memory          = var.platform_service_memory
    min_instances   = var.platform_service_min_instances
    max_instances   = var.platform_service_max_instances
    concurrency     = var.platform_service_concurrency
    timeout_seconds = var.platform_service_timeout_seconds
  }

  redis_config = {
    enable                  = var.enable_redis
    instance_name           = var.redis_instance_name
    memory_size_gb          = var.redis_memory_size_gb
    tier                    = var.redis_tier
    location_id             = var.redis_location_id
    alternative_location_id = var.redis_alternative_location_id
    replica_count           = var.redis_replica_count
    vpc_network_name        = var.vpc_network_name
    vpc_connector_cidr      = var.vpc_connector_cidr
  }

  ingestion_config = {
    prep_job_image  = var.ingestion_prep_job_image
    prep_job_cpu    = var.ingestion_prep_job_cpu
    prep_job_memory = var.ingestion_prep_job_memory
    prep_job_timeout = var.ingestion_prep_job_timeout
    ingestion_input_bucket_name = var.ingestion_input_bucket_name
    ingestion_input_folder = var.ingestion_input_folder
    ingestion_output_folder = var.ingestion_output_folder
    ingestion_input_bucket_location = var.ingestion_input_bucket_location
    create_ingestion_input_bucket   = var.create_ingestion_input_bucket
    
    deploy_workflow  = var.deploy_ingestion_workflow
    lock_timeout     = var.ingestion_lock_timeout
    helper_image     = var.ingestion_service_image
    create_ingestion_workflow_bucket = var.create_ingestion_workflow_bucket
    ingestion_workflow_bucket_name = var.ingestion_workflow_bucket_name
  }
}

module "stack" {
  # DO NOT CHANGE the format of the source line below. 
  # The Data Commons CLI relies on matching 'source = "./modules/stack"' to generate user scaffolding.
  source = "./modules/stack"

  global               = local.global_config
  spanner_config        = local.spanner_config
  bq_federation_config = local.bq_federation_config
  datacommons_service_config = local.datacommons_service_config
  platform_service_config    = local.platform_service_config
  redis_config         = local.redis_config
  ingestion_config     = local.ingestion_config

  depends_on = [google_project_service.apis]
}
