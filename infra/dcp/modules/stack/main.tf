data "google_compute_network" "default" {
  name = var.cdc.vpc_network_name
}

locals {
  enable_dcp = var.toggles.enable_dcp
  enable_cdc = var.toggles.enable_cdc

  cdc_use_spanner = var.toggles.enable_cdc && var.toggles.enable_dcp

  dcp_spanner_instance_id = local.enable_dcp ? module.spanner[0].spanner_instance_id : ""
  dcp_spanner_database_id = local.enable_dcp ? module.spanner[0].spanner_database_id : ""

  cdc_redis_host = local.enable_cdc && var.cdc.enable_redis ? module.cdc_redis[0].redis_host : ""
  cdc_redis_port = local.enable_cdc && var.cdc.enable_redis ? tostring(module.cdc_redis[0].redis_port) : ""

  cdc_cloud_run_shared_env_variables = local.enable_cdc ? [
    {
      name  = "USE_CLOUDSQL"
      value = local.cdc_use_spanner ? "false" : "true"
    },
    {
      name  = "CLOUDSQL_INSTANCE"
      value = local.cdc_use_spanner ? "" : module.cdc_mysql[0].mysql_instance_connection_name
    },
    {
      name  = "DB_NAME"
      value = var.cdc.mysql_database_name
    },
    {
      name  = "DB_USER"
      value = var.cdc.mysql_user
    },
    {
      name  = "DB_HOST"
      value = ""
    },
    {
      name  = "DB_PORT"
      value = "3306"
    },
    {
      name  = "OUTPUT_DIR"
      value = "gs://${module.storage.cdc_bucket_name}/${var.cdc.gcs_data_bucket_output_folder}"
    },
    {
      name  = "FORCE_RESTART"
      value = "${timestamp()}"
    },
    {
      name  = "REDIS_HOST"
      value = local.cdc_redis_host
    },
    {
      name  = "REDIS_PORT"
      value = local.cdc_redis_port
    },
    {
      name  = "GCP_SPANNER_INSTANCE_ID"
      value = local.dcp_spanner_instance_id
    },
    {
      name  = "GCP_SPANNER_DATABASE_NAME"
      value = local.dcp_spanner_database_id
    }
  ] : []

  cdc_cloud_run_shared_env_variable_secrets = local.enable_cdc ? concat([
    {
      name    = "DC_API_KEY"
      secret  = module.cdc_iam[0].dc_api_key_secret_id
      version = "latest"
    }
    ], var.cdc.disable_google_maps ? [] : [
    {
      name    = "MAPS_API_KEY"
      secret  = module.cdc_iam[0].maps_api_key_secret_id
      version = "latest"
    }
    ], local.cdc_use_spanner ? [] : [
    {
      name    = "DB_PASS"
      secret  = module.cdc_mysql[0].mysql_password_secret_id
      version = "latest"
    }
  ]) : []
}

module "spanner" {
  source = "../spanner"
  count  = local.enable_dcp ? 1 : 0

  namespace                = var.shared.namespace
  region                   = var.shared.region
  create_spanner_instance  = var.dcp.create_spanner_instance
  create_spanner_db        = var.dcp.create_spanner_db
  spanner_instance_id      = var.dcp.spanner_instance_id
  spanner_database_id      = var.dcp.spanner_database_id
  spanner_processing_units = var.dcp.spanner_processing_units
  deletion_protection      = var.shared.deletion_protection
}

module "dcp_service" {
  source = "../dcp_service"
  count  = local.enable_dcp ? 1 : 0

  namespace               = var.shared.namespace
  project_id              = var.shared.project_id
  region                  = var.shared.region
  image_url               = var.dcp.image_url
  service_name            = var.dcp.service_name
  service_account_name    = var.dcp.service_account_name
  service_cpu             = var.dcp.service_cpu
  service_memory          = var.dcp.service_memory
  service_min_instances   = var.dcp.service_min_instances
  service_max_instances   = var.dcp.service_max_instances
  service_concurrency     = var.dcp.service_concurrency
  service_timeout_seconds = var.dcp.service_timeout_seconds
  deletion_protection     = var.shared.deletion_protection
  make_service_public     = var.shared.make_services_public
  spanner_instance_id     = module.spanner[0].spanner_instance_id
  spanner_database_id     = module.spanner[0].spanner_database_id
}

module "storage" {
  source = "../storage"

  enable_dcp           = local.enable_dcp
  enable_cdc           = local.enable_cdc
  
  # DCP vars
  dcp_deploy                = var.dcp.deploy_data_ingestion_workflow
  dcp_create_bucket         = var.dcp.create_ingestion_bucket
  dcp_external_bucket_name  = var.dcp.external_ingestion_bucket_name
  dcp_region                 = var.shared.region
  dcp_deletion_protection   = var.shared.deletion_protection
  
  # CDC vars
  cdc_gcs_data_bucket_name     = var.cdc.gcs_data_bucket_name
  cdc_gcs_data_bucket_location = var.cdc.gcs_data_bucket_location
  
  # Shared vars
  project_id = var.shared.project_id
  namespace  = var.shared.namespace
}

module "dcp_ingestion_dataflow" {
  source = "../dcp_ingestion_dataflow"
  count  = local.enable_dcp ? 1 : 0

  deploy                = var.dcp.deploy_data_ingestion_workflow
  project_id            = var.shared.project_id
  namespace             = var.shared.namespace
  region                = var.shared.region
  deletion_protection   = var.shared.deletion_protection
  spanner_instance_id   = module.spanner[0].spanner_instance_id
  spanner_database_id   = module.spanner[0].spanner_database_id
  ingestion_bucket_name = module.storage.dcp_bucket_name
}

module "dcp_ingestion_helper" {
  source = "../dcp_ingestion_helper"
  count  = local.enable_dcp ? 1 : 0

  deploy                = var.dcp.deploy_data_ingestion_workflow
  project_id            = var.shared.project_id
  namespace             = var.shared.namespace
  region                = var.shared.region
  deletion_protection   = var.shared.deletion_protection
  spanner_instance_id   = module.spanner[0].spanner_instance_id
  spanner_database_id   = module.spanner[0].spanner_database_id
  ingestion_bucket_name = module.storage.dcp_bucket_name
  service_account_email = module.dcp_ingestion_dataflow[0].ingestion_runner_email
}

module "dcp_ingestion_workflow" {
  source = "../dcp_ingestion_workflow"
  count  = local.enable_dcp ? 1 : 0

  deploy                 = var.dcp.deploy_data_ingestion_workflow
  namespace              = var.shared.namespace
  region                 = var.shared.region
  deletion_protection    = var.shared.deletion_protection
  project_id             = var.shared.project_id
  ingestion_lock_timeout = var.dcp.ingestion_lock_timeout
  ingestion_helper_uri   = module.dcp_ingestion_helper[0].ingestion_helper_uri
  ingestion_runner_id    = module.dcp_ingestion_dataflow[0].ingestion_runner_id
  ingestion_runner_email = module.dcp_ingestion_dataflow[0].ingestion_runner_email
}



module "cdc_network" {
  source = "../cdc_network"
  count  = local.enable_cdc ? 1 : 0

  namespace          = var.shared.namespace
  region             = var.shared.region
  vpc_network_name   = var.cdc.vpc_network_name
  vpc_connector_cidr = var.cdc.vpc_connector_cidr
}

module "cdc_mysql" {
  source = "../cdc_mysql"
  count  = local.enable_cdc && !local.cdc_use_spanner ? 1 : 0

  namespace              = var.shared.namespace
  region                 = var.shared.region
  mysql_instance_name    = var.cdc.mysql_instance_name
  mysql_database_name    = var.cdc.mysql_database_name
  mysql_database_version = var.cdc.mysql_database_version
  mysql_cpu_count        = var.cdc.mysql_cpu_count
  mysql_memory_size_mb   = var.cdc.mysql_memory_size_mb
  mysql_user             = var.cdc.mysql_user
  deletion_protection    = var.shared.deletion_protection
}

module "cdc_redis" {
  source = "../cdc_redis"
  count  = local.enable_cdc && var.cdc.enable_redis ? 1 : 0

  namespace                     = var.shared.namespace
  region                        = var.shared.region
  redis_instance_name           = var.cdc.redis_instance_name
  redis_memory_size_gb          = var.cdc.redis_memory_size_gb
  redis_tier                    = var.cdc.redis_tier
  redis_location_id             = var.cdc.redis_location_id
  redis_alternative_location_id = var.cdc.redis_alternative_location_id
  redis_replica_count           = var.cdc.redis_replica_count
  vpc_network_id                = data.google_compute_network.default.id
}

module "cdc_iam" {
  source = "../cdc_iam"
  count  = local.enable_cdc ? 1 : 0

  project_id          = var.shared.project_id
  namespace           = var.shared.namespace
  dc_api_key          = var.cdc.dc_api_key
  maps_api_key        = var.cdc.maps_api_key
  disable_google_maps = var.cdc.disable_google_maps
  use_spanner         = local.cdc_use_spanner
}

module "cdc_data_ingestion_job" {
  source = "../cdc_data_ingestion_job"
  count  = local.enable_cdc ? 1 : 0

  project_id                    = var.shared.project_id
  namespace                     = var.shared.namespace
  region                        = var.shared.region
  deletion_protection           = var.shared.deletion_protection
  dc_data_job_image             = var.cdc.data_job_image
  dc_data_job_cpu               = var.cdc.data_job_cpu
  dc_data_job_memory            = var.cdc.data_job_memory
  dc_data_job_timeout           = var.cdc.data_job_timeout
  service_account_email         = module.cdc_iam[0].service_account_email
  vpc_connector_id              = module.cdc_network[0].connector_id
  bucket_name                   = module.storage.cdc_bucket_name
  gcs_data_bucket_input_folder  = var.cdc.gcs_data_bucket_input_folder
  gcs_data_bucket_output_folder = var.cdc.gcs_data_bucket_output_folder
  run_db_init                   = !local.cdc_use_spanner
  env_vars                      = local.cdc_cloud_run_shared_env_variables
  secret_env_vars               = local.cdc_cloud_run_shared_env_variable_secrets
}

module "cdc_services" {
  source = "../cdc_services"
  count  = local.enable_cdc ? 1 : 0

  project_id                        = var.shared.project_id
  namespace                         = var.shared.namespace
  region                            = var.shared.region
  deletion_protection               = var.shared.deletion_protection
  dc_web_service_image              = var.cdc.web_service_image
  dc_web_service_cpu                = var.cdc.web_service_cpu
  dc_web_service_memory             = var.cdc.web_service_memory
  dc_web_service_min_instance_count = var.cdc.web_service_min_instance_count
  dc_web_service_max_instance_count = var.cdc.web_service_max_instance_count
  make_dc_web_service_public        = var.shared.make_services_public
  google_analytics_tag_id           = var.cdc.google_analytics_tag_id
  dc_search_scope                   = var.cdc.search_scope
  enable_mcp                        = var.cdc.enable_mcp
  service_account_email             = module.cdc_iam[0].service_account_email
  vpc_connector_id                  = module.cdc_network[0].connector_id
  use_spanner                       = local.cdc_use_spanner
  mysql_connection_name             = local.cdc_use_spanner ? "" : module.cdc_mysql[0].mysql_instance_connection_name
  env_vars                          = local.cdc_cloud_run_shared_env_variables
  secret_env_vars                   = local.cdc_cloud_run_shared_env_variable_secrets

  depends_on = [module.cdc_data_ingestion_job]
}

check "spanner_instance_id_provided" {
  assert {
    condition     = !var.toggles.enable_dcp || var.dcp.create_spanner_instance || var.dcp.spanner_instance_id != ""
    error_message = "dcp_spanner_instance_id must be provided when reusing an existing instance (dcp_create_spanner_instance = false)."
  }
}
