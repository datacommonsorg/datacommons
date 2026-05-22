data "google_compute_network" "default" {
  name = var.redis_config.vpc_network_name
}

locals {

  redis_host = var.redis_config.enable && length(module.redis) > 0 ? module.redis[0].redis_host : ""
  redis_port = var.redis_config.enable && length(module.redis) > 0 ? tostring(module.redis[0].redis_port) : ""

  cloud_run_shared_env_variables = [
    {
      name  = "USE_CLOUDSQL"
      value = "false"
    },
    {
      name  = "OUTPUT_DIR"
      value = "gs://${module.storage.ingestion_input_bucket_name}/${var.ingestion_config.ingestion_output_folder}"
    },
    {
      name  = "FORCE_RESTART"
      value = "${timestamp()}"
    },
    {
      name  = "REDIS_HOST"
      value = local.redis_host
    },
    {
      name  = "REDIS_PORT"
      value = local.redis_port
    },
    {
      name  = "GCP_SPANNER_INSTANCE_ID"
      value = module.spanner.spanner_instance_id
    },
    {
      name  = "GCP_SPANNER_DATABASE_NAME"
      value = module.spanner.spanner_database_id
    },
    {
      name  = "INGESTION_WORKFLOW_NAME"
      value = coalesce(module.ingestion_workflow.ingestion_orchestrator_name, "")
    },
    {
      name  = "TEMP_LOCATION"
      value = "gs://${module.storage.ingestion_input_bucket_name}/temp"
    },
    {
      name  = "PROJECT_ID"
      value = var.global.project_id
    },
    {
      name  = "WORKFLOW_LOCATION"
      value = var.global.region
    },
    {
      name  = "REGION"
      value = var.global.region
    },
    {
      name  = "USE_SPANNER_GRAPH"
      value = "true"
    }
  ]

  datacommons_services_secrets = var.datacommons_services_config.enable ? concat([
    {
      name    = "DC_API_KEY"
      secret  = module.auth.dc_api_key_secret_id
      version = "latest"
    }
    ], !var.datacommons_services_config.website_disable_google_maps_api ? [
    {
      name    = "MAPS_API_KEY"
      secret  = module.auth.maps_api_key_secret_id
      version = "latest"
    }
  ] : []) : []
}

module "spanner" {
  source = "../spanner"

  project_id               = var.global.project_id
  namespace                = var.global.namespace
  region                   = var.global.region
  create_spanner_instance  = var.spanner_config.create_instance
  create_spanner_db        = var.spanner_config.create_db
  spanner_instance_id      = var.spanner_config.instance_id
  spanner_database_id      = var.spanner_config.database_id
  spanner_processing_units = var.spanner_config.processing_units
  deletion_protection      = var.global.deletion_protection
  orchestrator_email       = coalesce(module.ingestion_dataflow.orchestrator_email, "")
  ingestion_helper_sa_email = coalesce(module.ingestion_dataflow.ingestion_runner_email, "")
  spanner_version_retention_period = var.spanner_config.version_retention_period
  enable_bigquery_connection       = var.spanner_config.enable_bigquery_connection
  bigquery_connection_name         = var.spanner_config.bigquery_connection_name
  create_bigquery_reservation           = var.spanner_config.create_bigquery_reservation
  bigquery_reservation_slot_capacity     = var.spanner_config.bigquery_reservation_slot_capacity
  bigquery_reservation_max_slots        = var.spanner_config.bigquery_reservation_max_slots
}


module "storage" {
  source = "../storage"

  # Ingestion Workflow Bucket Vars
  deploy_workflow        = var.ingestion_config.deploy_workflow
  create_workflow_bucket = var.ingestion_config.create_ingestion_workflow_bucket
  ingestion_workflow_bucket_name = var.ingestion_config.ingestion_workflow_bucket_name
  region                 = var.global.region
  deletion_protection    = var.global.deletion_protection
  
  # Ingestion Input Bucket Vars
  ingestion_input_bucket_name = var.ingestion_config.ingestion_input_bucket_name
  input_bucket_location       = var.ingestion_config.ingestion_input_bucket_location
  create_input_bucket         = var.ingestion_config.create_ingestion_input_bucket
  
  # Shared vars
  project_id         = var.global.project_id
  namespace          = var.global.namespace
  orchestrator_email = coalesce(module.ingestion_dataflow.orchestrator_email, "")
}

module "ingestion_dataflow" {
  source = "../ingestion/dataflow"

  deploy                = var.ingestion_config.deploy_workflow
  project_id            = var.global.project_id
  namespace             = var.global.namespace
  region                = var.global.region
  deletion_protection   = var.global.deletion_protection
  spanner_instance_id   = module.spanner.spanner_instance_id
  spanner_database_id   = module.spanner.spanner_database_id
  ingestion_bucket_name = module.storage.ingestion_workflow_bucket_name
}

module "ingestion_helper_service" {
  source = "../ingestion/helper_service"

  deploy                = var.ingestion_config.deploy_workflow
  project_id            = var.global.project_id
  namespace             = var.global.namespace
  region                = var.global.region
  deletion_protection   = var.global.deletion_protection
  spanner_instance_id   = module.spanner.spanner_instance_id
  spanner_database_id   = module.spanner.spanner_database_id
  bq_connection_id      = module.spanner.bq_connection_id
  ingestion_bucket_name  = module.storage.ingestion_workflow_bucket_name
  service_account_email  = module.ingestion_dataflow.ingestion_runner_email
  ingestion_helper_image = var.ingestion_config.helper_image
  orchestrator_email     = var.ingestion_config.deploy_workflow ? coalesce(module.ingestion_dataflow.orchestrator_email, "") : ""
}

module "ingestion_workflow" {
  source = "../ingestion/workflow"

  deploy                 = var.ingestion_config.deploy_workflow
  namespace              = var.global.namespace
  region                 = var.global.region
  deletion_protection    = var.global.deletion_protection
  project_id             = var.global.project_id
  ingestion_lock_timeout = var.ingestion_config.lock_timeout
  ingestion_helper_uri   = module.ingestion_helper_service.ingestion_helper_uri
  ingestion_runner_id    = module.ingestion_dataflow.ingestion_runner_id
  ingestion_runner_email = module.ingestion_dataflow.ingestion_runner_email
  orchestrator_email     = var.ingestion_config.deploy_workflow ? coalesce(module.ingestion_dataflow.orchestrator_email, "") : ""
  enable_bq_federation   = var.ingestion_config.enable_bigquery_postprocessing
  enable_datacommons_services = var.datacommons_services_config.enable
}



module "redis" {
  source = "../redis"
  count  = var.redis_config.enable ? 1 : 0

  namespace                     = var.global.namespace
  region                        = var.global.region
  redis_instance_name           = var.redis_config.instance_name
  redis_memory_size_gb          = var.redis_config.memory_size_gb
  redis_tier                    = var.redis_config.tier
  redis_location_id             = var.redis_config.location_id
  redis_alternative_location_id = var.redis_config.alternative_location_id
  redis_replica_count           = var.redis_config.replica_count
  vpc_network_id                = data.google_compute_network.default.id
  vpc_connector_cidr            = var.redis_config.vpc_connector_cidr
  enable_connector              = true
}

module "auth" {
  source = "../auth"

  project_id          = var.global.project_id
  namespace           = var.global.namespace
  dc_api_key          = var.auth_config.google_datacommons_api_key
  maps_api_key        = var.auth_config.google_maps_api_key
  create_maps_key     = var.auth_config.create_maps_key
  use_spanner         = true
}

module "ingestion_preprocessing_job" {
  source = "../ingestion/preprocessing_job"
  count  = var.ingestion_config.deploy_workflow ? 1 : 0

  project_id                    = var.global.project_id
  namespace                     = var.global.namespace
  region                        = var.global.region
  deletion_protection           = var.global.deletion_protection
  dc_data_job_image             = var.ingestion_config.prep_job_image
  dc_data_job_cpu               = var.ingestion_config.prep_job_cpu
  dc_data_job_memory            = var.ingestion_config.prep_job_memory
  dc_data_job_timeout           = var.ingestion_config.prep_job_timeout
  service_account_email         = module.auth.service_account_email
  vpc_connector_id              = var.redis_config.enable ? module.redis[0].connector_id : null
  bucket_name                   = module.storage.ingestion_input_bucket_name
  gcs_data_bucket_input_folder  = var.ingestion_config.ingestion_input_folder
  gcs_data_bucket_output_folder = var.ingestion_config.ingestion_output_folder
  run_db_init                   = false
  use_spanner                   = true
  env_vars                      = local.cloud_run_shared_env_variables
  secret_env_vars               = local.datacommons_services_secrets
  orchestrator_email            = coalesce(module.ingestion_dataflow.orchestrator_email, "")

  depends_on = [module.auth]
}

module "datacommons_services" {
  source = "../datacommons_services"
  count  = var.datacommons_services_config.enable ? 1 : 0

  project_id                        = var.global.project_id
  namespace                         = var.global.namespace
  region                            = var.global.region
  deletion_protection               = var.global.deletion_protection
  dc_web_service_image              = var.datacommons_services_config.image
  dc_web_service_cpu                = var.datacommons_services_config.cpu
  dc_web_service_memory             = var.datacommons_services_config.memory
  dc_web_service_min_instance_count = var.datacommons_services_config.min_instances
  dc_web_service_max_instance_count = var.datacommons_services_config.max_instances
  make_dc_web_service_public        = var.global.allow_unauthenticated_access
  google_analytics_tag_id           = var.datacommons_services_config.google_analytics_tag
  dc_search_scope                   = var.datacommons_services_config.search_scope
  enable_mcp                        = var.datacommons_services_config.enable_mcp
  prep_bucket_name                   = module.storage.ingestion_input_bucket_name
  service_account_email             = module.auth.service_account_email
  vpc_connector_id                  = var.redis_config.enable ? module.redis[0].connector_id : null
  use_spanner                       = true
  mysql_connection_name             = ""
  env_vars                          = local.cloud_run_shared_env_variables
  secret_env_vars                   = local.datacommons_services_secrets

  depends_on = [module.ingestion_preprocessing_job]
}

check "spanner_instance_id_provided" {
  assert {
    condition     = !var.datacommons_services_config.enable || var.spanner_config.create_instance || var.spanner_config.instance_id != ""
    error_message = "spanner_instance_id must be provided when reusing an existing instance (create_spanner_instance = false)."
  }
}

resource "google_storage_bucket_iam_member" "dataflow_bucket_access" {
  count  = var.ingestion_config.deploy_workflow ? 1 : 0
  bucket = module.storage.ingestion_input_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.ingestion_dataflow.ingestion_runner_email}"
}

# This is only needed to trigger the services restart to pick up the GCS embeddings change
resource "google_service_account_iam_member" "ingestion_runner_act_as_sa" {
  count              = var.ingestion_config.deploy_workflow ? 1 : 0
  service_account_id = "projects/${var.global.project_id}/serviceAccounts/${module.auth.service_account_email}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${module.ingestion_dataflow.ingestion_runner_email}"
}

