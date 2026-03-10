# Local variable definitions

locals {
  # Data Commons Data Bucket
  gcs_data_bucket_name = var.gcs_data_bucket_name != "" ? var.gcs_data_bucket_name : "${var.namespace}-datacommons-data-${var.project_id}"

  # Use var.maps_api_key if set, otherwise use generated Maps API key
  maps_api_key = var.maps_api_key != null ? var.maps_api_key : google_apikeys_key.maps_api_key[0].key_string

  # Data Commons API hostname
  dc_api_hostname = "api.datacommons.org"

  # Data Commons API protocol
  dc_api_protocol = "https"

  # Data Commons API root URL
  dc_api_root = "${local.dc_api_protocol}://${local.dc_api_hostname}"

  # Optionally-configured Redis instance
  redis_instance = var.enable_redis ? google_redis_instance.redis_instance[0] : null


  # Shared environment variables used by the Data Commons web service and the Data
  # Commons data loading job
  cloud_run_shared_env_variables = [
    {
      name  = "USE_CLOUDSQL"
      value = "true"
    },
    {
      name  = "CLOUDSQL_INSTANCE"
      value = google_sql_database_instance.mysql_instance.connection_name
    },
    {
      name  = "DB_NAME"
      value = var.mysql_database_name
    },
    {
      name  = "DB_USER"
      value = var.mysql_user
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
      value = "gs://${local.gcs_data_bucket_name}/${var.gcs_data_bucket_output_folder}"
    },
    {
      name  = "FORCE_RESTART"
      value = "${timestamp()}"
    },
    {
      name  = "REDIS_HOST"
      value = try(local.redis_instance.host, "")
    },
    {
      name  = "REDIS_PORT"
      value = try(local.redis_instance.port, "")
    }
  ]

  # Shared environment variables containing secret refs used by the Data Commons
  # web service and the Data Commons data loading job
  cloud_run_shared_env_variable_secrets = [
    {
      name = "DC_API_KEY"
      value_source = {
        secret_key_ref = {
          secret  = google_secret_manager_secret.dc_api_key.secret_id
          version = "latest"
        }
      }
    },
    {
      name = "DB_PASS"
      value_source = {
        secret_key_ref = {
          secret  = google_secret_manager_secret.mysql_password_secret.secret_id
          version = "latest"
        }
      }
    }
  ]
}
