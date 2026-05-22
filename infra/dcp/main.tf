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
    ], var.enable_spanner ? ["spanner.googleapis.com"] : [],
    var.enable_ingestion ? [
      "workflows.googleapis.com",
      "workflowexecutions.googleapis.com",
      "dataflow.googleapis.com"
      ] : [], var.spanner_enable_bigquery_connection ? [
      "bigqueryconnection.googleapis.com",
      "bigquery.googleapis.com",
      "bigqueryreservation.googleapis.com"
  ] : []))

  service            = each.key
  disable_on_destroy = false
}

locals {
  global_config = {
    project_id          = var.project_id
    region              = var.region
    namespace           = var.namespace
    deletion_protection = var.deletion_protection
  }

  spanner_config = {
    enable                             = var.enable_spanner
    create_instance                    = var.spanner_create_instance
    create_db                          = var.spanner_create_database
    instance_id                        = var.spanner_instance_id
    database_id                        = var.spanner_database_id
    version_retention_period           = var.spanner_version_retention_period
    processing_units                   = var.spanner_processing_units
    enable_bigquery_connection         = var.spanner_enable_bigquery_connection
    bigquery_connection_name           = var.spanner_bigquery_connection_name
    create_bigquery_reservation        = var.spanner_create_bigquery_reservation
    bigquery_reservation_slot_capacity = var.spanner_bigquery_reservation_slot_capacity
    bigquery_reservation_max_slots     = var.spanner_bigquery_reservation_max_slots
  }


  datacommons_services_config = {
    enable                          = var.enable_datacommons_services
    image                           = var.datacommons_services_image
    name                            = var.datacommons_services_name
    min_instances                   = var.datacommons_services_min_instances
    max_instances                   = var.datacommons_services_max_instances
    cpu                             = var.datacommons_services_cpu
    memory                          = var.datacommons_services_memory
    google_analytics_tag            = var.datacommons_services_google_analytics_tag_id
    enable_mcp                      = var.datacommons_services_enable_mcp
    search_scope                    = var.datacommons_services_mcp_search_scope
    instructions_path               = var.datacommons_services_mcp_instructions_path
    allow_unauthenticated_access    = var.datacommons_services_allow_unauthenticated_access
    website_disable_google_maps_api = var.datacommons_services_website_disable_google_maps_api
  }

  auth_config = {
    google_datacommons_api_key = var.auth_google_datacommons_api_key
    google_maps_api_key        = var.auth_google_maps_api_key
    create_google_maps_key     = var.auth_create_google_maps_api_key
  }





  redis_config = {
    enable                  = var.enable_redis
    instance_name           = var.redis_instance_name
    memory_size_gb          = var.redis_memory_size_gb
    tier                    = var.redis_tier
    location_id             = var.redis_location_id
    alternative_location_id = var.redis_alternative_location_id
    replica_count           = var.redis_replica_count
    vpc_network_name        = var.redis_vpc_network_name
    vpc_connector_cidr      = var.redis_vpc_connector_cidr
  }

  ingestion_config = {
    # Global Toggles
    enable_ingestion                        = var.enable_ingestion
    workflow_enable_bigquery_postprocessing = var.ingestion_workflow_enable_bigquery_postprocessing

    # Storage & Paths
    input_path              = var.ingestion_input_path
    workflow_artifacts_path = var.ingestion_workflow_artifacts_path

    # Preprocessing Job
    preprocessing_job_image   = var.ingestion_preprocessing_job_image
    preprocessing_job_cpu     = var.ingestion_preprocessing_job_cpu
    preprocessing_job_memory  = var.ingestion_preprocessing_job_memory
    preprocessing_job_timeout = var.ingestion_preprocessing_job_timeout

    # Workflow & Helper Service
    workflow_lock_acquisition_timeout = var.ingestion_workflow_lock_acquisition_timeout
    helper_service_image              = var.ingestion_helper_service_image
  }
}

module "stack" {
  # DO NOT CHANGE the format of the source line below. 
  # The Data Commons CLI relies on matching 'source = "./modules/stack"' to generate user scaffolding.
  source = "./modules/stack"

  global                          = local.global_config
  spanner_config                  = local.spanner_config
  storage_create_artifacts_bucket = var.storage_create_artifacts_bucket
  storage_artifacts_bucket_name   = var.storage_artifacts_bucket_name
  datacommons_services_config     = local.datacommons_services_config
  auth_config                     = local.auth_config
  redis_config                    = local.redis_config
  ingestion_config                = local.ingestion_config

  depends_on = [google_project_service.apis]
}
