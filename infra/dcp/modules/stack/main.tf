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
      value = "gs://${module.storage.artifacts_bucket_name}/${var.ingestion_config.workflow_artifacts_path}"
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
      name = "GCP_SPANNER_INSTANCE_ID"
      # Use index [0] because module.spanner is now conditional (count). Fallback to empty string if disabled.
      value = var.spanner_config.enable ? module.spanner[0].spanner_instance_id : ""
    },
    {
      name = "GCP_SPANNER_DATABASE_NAME"
      # Use index [0] because module.spanner is now conditional (count). Fallback to empty string if disabled.
      value = var.spanner_config.enable ? module.spanner[0].spanner_database_id : ""
    },
    {
      name = "INGESTION_WORKFLOW_NAME"
      # Fallback to empty string if ingestion is disabled and module output is null
      value = module.ingestion_workflow.workflow_name != null ? module.ingestion_workflow.workflow_name : ""
    },
    {
      name  = "TEMP_LOCATION"
      value = "gs://${module.storage.artifacts_bucket_name}/temp"
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
  count  = var.spanner_config.enable ? 1 : 0

  project_id                         = var.global.project_id
  namespace                          = var.global.namespace
  region                             = var.global.region
  create_instance                    = var.spanner_config.create_instance
  create_database                    = var.spanner_config.create_db
  instance_id                        = var.spanner_config.instance_id
  database_id                        = var.spanner_config.database_id
  processing_units                   = var.spanner_config.processing_units
  deletion_protection                = var.global.deletion_protection
  version_retention_period           = var.spanner_config.version_retention_period
  enable_bigquery_connection         = var.spanner_config.enable_bigquery_connection
  bigquery_connection_name           = var.spanner_config.bigquery_connection_name
  create_bigquery_reservation        = var.spanner_config.create_bigquery_reservation
  bigquery_reservation_slot_capacity = var.spanner_config.bigquery_reservation_slot_capacity
  bigquery_reservation_max_slots     = var.spanner_config.bigquery_reservation_max_slots
}


module "storage" {
  source = "../storage"

  # Ingestion Workflow Bucket Vars
  create_artifacts_bucket = var.storage_create_artifacts_bucket
  artifacts_bucket_name   = var.storage_artifacts_bucket_name
  region                  = var.global.region
  deletion_protection     = var.global.deletion_protection

  # Shared vars
  project_id = var.global.project_id
  namespace  = var.global.namespace
}

module "ingestion_preprocessing_job" {
  source = "../ingestion/preprocessing_job"
  count  = var.ingestion_config.enable_ingestion ? 1 : 0

  project_id              = var.global.project_id
  namespace               = var.global.namespace
  region                  = var.global.region
  deletion_protection     = var.global.deletion_protection
  image                   = var.ingestion_config.preprocessing_job_image
  cpu                     = var.ingestion_config.preprocessing_job_cpu
  memory                  = var.ingestion_config.preprocessing_job_memory
  timeout                 = var.ingestion_config.preprocessing_job_timeout
  vpc_connector_id        = var.redis_config.enable ? module.redis[0].connector_id : null
  bucket_name             = module.storage.artifacts_bucket_name
  input_path              = var.ingestion_config.input_path
  workflow_artifacts_path = var.ingestion_config.workflow_artifacts_path
  run_database_init       = false
  use_spanner             = true
  env_vars                = local.cloud_run_shared_env_variables
  secret_env_vars         = local.datacommons_services_secrets
  dc_api_key_secret_id    = module.auth.dc_api_key_secret_id
  maps_api_key_secret_id  = module.auth.maps_api_key_secret_id

  depends_on = [module.auth]
}

module "ingestion_dataflow" {
  source = "../ingestion/dataflow"

  deploy                = var.ingestion_config.enable_ingestion
  project_id            = var.global.project_id
  namespace             = var.global.namespace
  ingestion_bucket_name = module.storage.artifacts_bucket_name
  use_spanner           = var.spanner_config.enable
}


module "ingestion_helper_service" {
  source = "../ingestion/helper_service"

  deploy              = var.ingestion_config.enable_ingestion
  project_id          = var.global.project_id
  namespace           = var.global.namespace
  region              = var.global.region
  deletion_protection = var.global.deletion_protection
  # Use index [0] because module.spanner is conditional. Fallback to empty string if disabled.
  spanner_instance_id    = var.spanner_config.enable ? module.spanner[0].spanner_instance_id : ""
  spanner_database_id    = var.spanner_config.enable ? module.spanner[0].spanner_database_id : ""
  bigquery_connection_id = var.spanner_config.enable ? module.spanner[0].bigquery_connection_id : ""
  ingestion_bucket_name  = module.storage.artifacts_bucket_name
  image                  = var.ingestion_config.helper_service_image
<<<<<<< Updated upstream
  use_spanner            = var.spanner_config.enable
=======
  bigquery_job_service_account = module.ingestion_dataflow.service_account_email
>>>>>>> Stashed changes
}


module "ingestion_workflow" {
  source = "../ingestion/workflow"

  deploy                         = var.ingestion_config.enable_ingestion
  namespace                      = var.global.namespace
  region                         = var.global.region
  deletion_protection            = var.global.deletion_protection
  project_id                     = var.global.project_id
  lock_acquisition_timeout       = var.ingestion_config.workflow_lock_acquisition_timeout
  ingestion_helper_uri           = module.ingestion_helper_service.ingestion_helper_uri
  dataflow_service_account_email = module.ingestion_dataflow.service_account_email
  enable_bigquery_postprocessing = var.ingestion_config.workflow_enable_bigquery_postprocessing
  enable_datacommons_services    = var.datacommons_services_config.enable
  ingestion_helper_service_name  = "${var.global.namespace != "" ? "${var.global.namespace}-" : ""}dc-ingestion-helper"

  depends_on = [module.ingestion_helper_service]
}



module "redis" {
  source = "../redis"
  count  = var.redis_config.enable ? 1 : 0

  namespace               = var.global.namespace
  region                  = var.global.region
  instance_name           = var.redis_config.instance_name
  memory_size_gb          = var.redis_config.memory_size_gb
  tier                    = var.redis_config.tier
  location_id             = var.redis_config.location_id
  alternative_location_id = var.redis_config.alternative_location_id
  replica_count           = var.redis_config.replica_count
  vpc_network_id          = data.google_compute_network.default.id
  vpc_connector_cidr      = var.redis_config.vpc_connector_cidr
  enable_connector        = true
}

module "auth" {
  source = "../auth"

  project_id             = var.global.project_id
  namespace              = var.global.namespace
  dc_api_key             = var.auth_config.google_datacommons_api_key
  google_maps_api_key    = var.auth_config.google_maps_api_key
  create_google_maps_key = var.auth_config.create_google_maps_key
}

module "datacommons_services" {
  source = "../datacommons_services"
  count  = var.datacommons_services_config.enable ? 1 : 0

  project_id              = var.global.project_id
  namespace               = var.global.namespace
  region                  = var.global.region
  deletion_protection     = var.global.deletion_protection
  image                   = var.datacommons_services_config.image
  cpu                     = var.datacommons_services_config.cpu
  memory                  = var.datacommons_services_config.memory
  min_instances           = var.datacommons_services_config.min_instances
  max_instances           = var.datacommons_services_config.max_instances
  make_public             = var.datacommons_services_config.allow_unauthenticated_access
  google_analytics_tag_id = var.datacommons_services_config.google_analytics_tag
  mcp_search_scope        = var.datacommons_services_config.search_scope
  enable_mcp              = var.datacommons_services_config.enable_mcp
  mcp_instructions_path   = var.datacommons_services_config.instructions_path
  artifacts_bucket_name   = module.storage.artifacts_bucket_name
  vpc_connector_id        = var.redis_config.enable ? module.redis[0].connector_id : null
  use_spanner             = var.spanner_config.enable
  env_vars                = local.cloud_run_shared_env_variables
  secret_env_vars         = local.datacommons_services_secrets

  depends_on = [module.ingestion_preprocessing_job]
}

check "spanner_instance_id_provided" {
  assert {
    condition     = !var.spanner_config.enable || var.spanner_config.create_instance || var.spanner_config.instance_id != ""
    error_message = "spanner_instance_id must be provided when reusing an existing instance (create_spanner_instance = false)."
  }
}

check "datacommons_api_key_provided" {
  assert {
    condition     = (!var.datacommons_services_config.enable && !var.ingestion_config.enable_ingestion) || var.auth_config.google_datacommons_api_key != ""
    error_message = "auth_google_datacommons_api_key must be provided when datacommons_services or ingestion are enabled."
  }
}




# =============================================================================
# Cross-Module IAM Bindings
# =============================================================================

resource "google_storage_bucket_iam_member" "dataflow_bucket_access" {
  count  = var.ingestion_config.enable_ingestion ? 1 : 0
  bucket = module.storage.artifacts_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.ingestion_dataflow.service_account_email}"
}

# This is only needed to trigger the services restart to pick up the GCS embeddings change
# Mandatory dependency: The Ingestion Workflow service account needs to act as the Serving service account
# to perform the service restart step via the Cloud Run API after ingestion completes.
resource "google_service_account_iam_member" "ingestion_workflow_act_as_serving_sa" {
  count              = var.ingestion_config.enable_ingestion && var.datacommons_services_config.enable ? 1 : 0
  service_account_id = "projects/${var.global.project_id}/serviceAccounts/${module.datacommons_services[0].service_account_email}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${module.ingestion_workflow.service_account_email}"
}



resource "google_spanner_database_iam_member" "workflow_spanner_user" {
  # Only create if ingestion is enabled and Spanner is enabled!
  count = var.ingestion_config.enable_ingestion && var.spanner_config.enable ? 1 : 0
  # Use index [0] because module.spanner is conditional.
  instance = module.spanner[0].spanner_instance_id
  database = module.spanner[0].spanner_database_id
  role     = "roles/spanner.databaseUser"
  member   = "serviceAccount:${module.ingestion_workflow.service_account_email}"
}



resource "google_storage_bucket_iam_member" "workflow_bucket_access" {
  count  = var.ingestion_config.enable_ingestion ? 1 : 0
  bucket = module.storage.artifacts_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.ingestion_workflow.service_account_email}"
}

resource "google_cloud_run_v2_job_iam_member" "workflow_pre_viewer" {
  count    = var.ingestion_config.enable_ingestion ? 1 : 0
  location = var.global.region
  name     = module.ingestion_preprocessing_job[0].job_name
  role     = "roles/run.viewer"
  member   = "serviceAccount:${module.ingestion_workflow.service_account_email}"
}

resource "google_cloud_run_v2_job_iam_member" "workflow_pre_invoker" {
  count    = var.ingestion_config.enable_ingestion ? 1 : 0
  location = var.global.region
  name     = module.ingestion_preprocessing_job[0].job_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.ingestion_workflow.service_account_email}"
}

resource "google_storage_bucket_iam_member" "preprocessing_bucket_access" {
  count  = var.ingestion_config.enable_ingestion ? 1 : 0
  bucket = module.storage.artifacts_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.ingestion_preprocessing_job[0].service_account_email}"
}



resource "google_project_iam_member" "workflow_dataflow_developer" {
  count   = var.ingestion_config.enable_ingestion ? 1 : 0
  project = var.global.project_id
  role    = "roles/dataflow.developer"
  member  = "serviceAccount:${module.ingestion_workflow.service_account_email}"
}

resource "google_cloud_run_v2_service_iam_member" "workflow_serving_developer" {
  count    = var.ingestion_config.enable_ingestion && var.datacommons_services_config.enable ? 1 : 0
  location = var.global.region
  name     = module.datacommons_services[0].service_name
  role     = "roles/run.developer"
  member   = "serviceAccount:${module.ingestion_workflow.service_account_email}"
}





