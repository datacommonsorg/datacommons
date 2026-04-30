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

# Enable required APIs for both stacks
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
    "workflowexecutions.googleapis.com"
  ] : []))

  service            = each.key
  disable_on_destroy = false
}

# --- Network Data Sources ---
data "google_compute_network" "default" {
  name = var.cdc_vpc_network_name
}

data "google_compute_subnetwork" "default" {
  name   = var.cdc_vpc_network_subnet_name
  region = var.region
}

# --- Data Commons Platform (DCP) Stack ---
module "dcp" {
  source = "./modules/dcp"
  count  = var.enable_dcp ? 1 : 0

  project_id               = var.project_id
  namespace                = var.namespace
  region                   = var.region
  image_url                = var.dcp_image_url
  service_name             = var.dcp_service_name
  service_account_name     = var.dcp_service_account_name
  create_spanner_instance  = var.dcp_create_spanner_instance
  create_spanner_db        = var.dcp_create_spanner_db
  spanner_instance_id      = var.dcp_spanner_instance_id
  spanner_database_id      = var.dcp_spanner_database_id
  spanner_processing_units = var.dcp_spanner_processing_units
  service_cpu              = var.dcp_service_cpu
  service_memory           = var.dcp_service_memory
  service_min_instances    = var.dcp_service_min_instances
  service_max_instances    = var.dcp_service_max_instances
  service_concurrency      = var.dcp_service_concurrency
  service_timeout_seconds  = var.dcp_service_timeout_seconds
  make_service_public      = var.make_services_public
  deletion_protection      = var.deletion_protection

  deploy_data_ingestion_workflow = var.dcp_deploy_data_ingestion_workflow


  depends_on = [google_project_service.apis]
}

# --- Custom Data Commons (CDC) Legacy Stack ---
module "cdc" {
  source = "./modules/cdc"
  count  = var.enable_cdc ? 1 : 0

  project_id                        = var.project_id
  namespace                         = var.namespace
  dc_api_key                        = var.cdc_dc_api_key
  maps_api_key                      = var.cdc_maps_api_key
  disable_google_maps               = var.cdc_disable_google_maps
  region                            = var.region
  google_analytics_tag_id           = var.cdc_google_analytics_tag_id
  gcs_data_bucket_name              = var.cdc_gcs_data_bucket_name
  gcs_data_bucket_input_folder      = var.cdc_gcs_data_bucket_input_folder
  gcs_data_bucket_output_folder     = var.cdc_gcs_data_bucket_output_folder
  gcs_data_bucket_location          = var.cdc_gcs_data_bucket_location
  mysql_instance_name               = var.cdc_mysql_instance_name
  mysql_database_name               = var.cdc_mysql_database_name
  mysql_database_version            = var.cdc_mysql_database_version
  mysql_cpu_count                   = var.cdc_mysql_cpu_count
  mysql_memory_size_mb              = var.cdc_mysql_memory_size_mb
  mysql_storage_size_gb             = var.cdc_mysql_storage_size_gb
  mysql_user                        = var.cdc_mysql_user
  mysql_deletion_protection         = var.deletion_protection
  dc_web_service_image              = var.cdc_web_service_image
  dc_web_service_min_instance_count = var.cdc_web_service_min_instance_count
  dc_web_service_max_instance_count = var.cdc_web_service_max_instance_count
  dc_web_service_cpu                = var.cdc_web_service_cpu
  dc_web_service_memory             = var.cdc_web_service_memory
  make_dc_web_service_public        = var.make_services_public
  dc_data_job_image                 = var.cdc_data_job_image
  dc_data_job_cpu                   = var.cdc_data_job_cpu
  dc_data_job_memory                = var.cdc_data_job_memory
  dc_data_job_timeout               = var.cdc_data_job_timeout
  dc_search_scope                   = var.cdc_search_scope
  enable_mcp                        = var.cdc_enable_mcp
  vpc_network_name                  = var.cdc_vpc_network_name
  vpc_network_subnet_name           = var.cdc_vpc_network_subnet_name
  enable_redis                      = var.cdc_enable_redis
  redis_instance_name               = var.cdc_redis_instance_name
  redis_memory_size_gb              = var.cdc_redis_memory_size_gb
  redis_tier                        = var.cdc_redis_tier
  redis_location_id                 = var.cdc_redis_location_id
  redis_alternative_location_id     = var.cdc_redis_alternative_location_id
  redis_replica_count               = var.cdc_redis_replica_count
  vpc_connector_cidr                = var.cdc_vpc_connector_cidr
  vpc_network_id                    = data.google_compute_network.default.id
  use_spanner                       = var.enable_dcp
  spanner_instance_id               = var.enable_dcp ? module.dcp[0].spanner_instance_id : ""
  spanner_database_id               = var.enable_dcp ? module.dcp[0].spanner_database_id : ""
  workflow_name                     = var.enable_dcp && var.dcp_deploy_data_ingestion_workflow ? module.dcp[0].ingestion_orchestrator_name : ""
  deletion_protection               = var.deletion_protection

  depends_on = [google_project_service.apis]
}

# Ensure Spanner instance ID is provided when not creating a new one
check "spanner_instance_id_provided" {
  assert {
    condition     = !var.enable_dcp || var.dcp_create_spanner_instance || var.dcp_spanner_instance_id != ""
    error_message = "dcp_spanner_instance_id must be provided when reusing an existing instance (dcp_create_spanner_instance = false)."
  }
}
