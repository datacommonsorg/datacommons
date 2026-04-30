# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Custom Data Commons terraform resources

# Generate a random suffix to prevent 7-day naming collisions on recreation
resource "random_id" "mysql_suffix" {
  count       = var.use_spanner ? 0 : 1
  byte_length = 4
}

# Cloud SQL instance for Data Commons
resource "google_sql_database_instance" "mysql_instance" {
  count            = var.use_spanner ? 0 : 1
  name             = "${local.name_prefix}${var.mysql_instance_name}-${random_id.mysql_suffix[0].hex}"
  database_version = var.mysql_database_version
  region           = var.region

  settings {
    tier = "db-custom-${var.mysql_cpu_count}-${var.mysql_memory_size_mb}"
    ip_configuration {
      ipv4_enabled = true
    }
    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = var.deletion_protection
}

# MySQL Database
resource "google_sql_database" "mysql_db" {
  count    = var.use_spanner ? 0 : 1
  name     = var.mysql_database_name
  instance = google_sql_database_instance.mysql_instance[0].name
}

# Generate a random password for the MySQL user
resource "random_password" "mysql_password" {
  length  = 16
  special = true
}

# Store MySQL password in Secret Manager
resource "google_secret_manager_secret" "mysql_password_secret" {
  count     = var.use_spanner ? 0 : 1
  secret_id = "${local.name_prefix}mysql-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "mysql_password_secret_version" {
  count       = var.use_spanner ? 0 : 1
  secret      = google_secret_manager_secret.mysql_password_secret[0].id
  secret_data = random_password.mysql_password.result
}

# MySQL User
resource "google_sql_user" "mysql_user" {
  count    = var.use_spanner ? 0 : 1
  name     = var.mysql_user
  instance = google_sql_database_instance.mysql_instance[0].name
  password = random_password.mysql_password.result
}

# Optional Redis instance
resource "google_redis_instance" "redis_instance" {
  count                   = var.enable_redis ? 1 : 0
  name                    = "${local.name_prefix}${var.redis_instance_name}"
  memory_size_gb          = var.redis_memory_size_gb
  tier                    = var.redis_tier
  region                  = var.region
  location_id             = var.redis_location_id
  alternative_location_id = var.redis_alternative_location_id
  redis_version           = "REDIS_6_X"
  display_name            = "Data Commons Redis Instance"
  reserved_ip_range       = null
  replica_count           = var.redis_replica_count
  authorized_network      = var.vpc_network_id
  connect_mode            = "DIRECT_PEERING"
}

# VPC Access Connector for private connections
resource "google_vpc_access_connector" "connector" {
  name          = "${local.name_prefix}vpc-conn"
  region        = var.region
  network       = var.vpc_network_name
  ip_cidr_range = var.vpc_connector_cidr
  min_instances = 2
  max_instances = 10
}

# GCS Bucket for data storage
resource "google_storage_bucket" "data_bucket" {
  name          = local.gcs_data_bucket_name
  location      = var.gcs_data_bucket_location
  force_destroy = true

  uniform_bucket_level_access = true
}

# Maps API Key
resource "google_apikeys_key" "maps_api_key" {
  count        = var.maps_api_key == null && !var.disable_google_maps ? 1 : 0
  name         = "${local.name_prefix}maps-key"
  display_name = "Maps API Key for ${var.namespace != "" ? var.namespace : "Data Commons"}"
  project      = var.project_id

  restrictions {
    api_targets {
      service = "maps-backend.googleapis.com"
    }
    api_targets {
      service = "places_backend"
    }
  }
}

# Cloud Run job for data management
resource "google_cloud_run_v2_job" "dc_data_job" {
  name                = "${local.name_prefix}datacommons-data-job"
  location            = var.region
  deletion_protection = var.deletion_protection

  template {
    template {
      containers {
        image = var.dc_data_job_image
        resources {
          limits = {
            cpu    = var.dc_data_job_cpu
            memory = var.dc_data_job_memory
          }
        }
        dynamic "env" {
          for_each = local.cloud_run_shared_env_variables
          content {
            name  = env.value.name
            value = env.value.value
          }
        }

        dynamic "env" {
          for_each = local.cloud_run_shared_env_variable_secrets
          content {
            name = env.value.name
            value_source {
              secret_key_ref {
                secret  = env.value.value_source.secret_key_ref.secret
                version = env.value.value_source.secret_key_ref.version
              }
            }
          }
        }

        env {
          name  = "GCS_BUCKET"
          value = google_storage_bucket.data_bucket.name
        }
        env {
          name  = "GCS_INPUT_FOLDER"
          value = var.gcs_data_bucket_input_folder
        }
        env {
          name  = "GCS_OUTPUT_FOLDER"
          value = var.gcs_data_bucket_output_folder
        }
        env {
          name  = "INPUT_DIR"
          value = "gs://${google_storage_bucket.data_bucket.name}/${var.gcs_data_bucket_input_folder}"
        }
        env {
          name  = "WORKFLOW_NAME"
          value = var.workflow_name
        }
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "WORKFLOW_LOCATION"
          value = var.region
        }
        env {
          name  = "TEMP_LOCATION"
          value = "gs://${google_storage_bucket.data_bucket.name}/temp"
        }
        env {
          name  = "REGION"
          value = var.region
        }
      }
      vpc_access {
        connector = google_vpc_access_connector.connector.id
        egress    = "PRIVATE_RANGES_ONLY"
      }
      max_retries     = 0
      timeout         = var.dc_data_job_timeout
      service_account = google_service_account.datacommons_service_account.email
    }
  }

  depends_on = [
    google_secret_manager_secret_version.mysql_password_secret_version,
    google_secret_manager_secret_version.dc_api_key_version,
    google_secret_manager_secret_version.maps_api_key_version
  ]
}

# Run the db init job on terraform apply to create tables
resource "null_resource" "run_db_init" {
  count = var.use_spanner ? 0 : 1

  depends_on = [
    google_cloud_run_v2_job.dc_data_job
  ]

  triggers = {
    # Run once per deployment or when the job image changes
    job_image = var.dc_data_job_image
  }

  provisioner "local-exec" {
    command = <<EOT
      gcloud run jobs execute ${local.name_prefix}datacommons-data-job \
        --update-env-vars DATA_RUN_MODE=schemaupdate \
        --region=${var.region} \
        --project=${var.project_id} \
        --wait
EOT
  }
}

# Cloud Run service for Data Commons website
resource "google_cloud_run_v2_service" "dc_web_service" {
  name                = "${local.name_prefix}datacommons-web-service"
  location            = var.region
  deletion_protection = var.deletion_protection

  template {
    timeout = "300s"
    containers {
      image = var.dc_web_service_image
      resources {
        limits = {
          cpu    = var.dc_web_service_cpu
          memory = var.dc_web_service_memory
        }
      }
      ports {
        container_port = 8080
      }

      startup_probe {
        timeout_seconds   = 120
        period_seconds    = 30
        failure_threshold = 6
        tcp_socket {
          port = 8080
        }
      }

      dynamic "env" {
        for_each = local.cloud_run_shared_env_variables
        content {
          name  = env.value.name
          value = env.value.value
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      dynamic "env" {
        for_each = local.cloud_run_shared_env_variable_secrets
        content {
          name = env.value.name
          value_source {
            secret_key_ref {
              secret  = env.value.value_source.secret_key_ref.secret
              version = env.value.value_source.secret_key_ref.version
            }
          }
        }
      }

      env {
        name  = "GOOGLE_ANALYTICS_TAG_ID"
        value = var.google_analytics_tag_id != null ? var.google_analytics_tag_id : ""
      }
      env {
        name  = "DC_SEARCH_SCOPE"
        value = var.dc_search_scope
      }
      env {
        name  = "ENABLE_MCP"
        value = var.enable_mcp ? "true" : "false"
      }
    }
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }
    scaling {
      min_instance_count = var.dc_web_service_min_instance_count
      max_instance_count = var.dc_web_service_max_instance_count
    }
    service_account = google_service_account.datacommons_service_account.email
    dynamic "volumes" {
      for_each = var.use_spanner ? [] : [1]
      content {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.mysql_instance[0].connection_name]
        }
      }
    }
  }
  depends_on = [
    null_resource.run_db_init
  ]
}

# Make the service public if requested
resource "google_cloud_run_service_iam_member" "public_access" {
  count    = var.make_dc_web_service_public ? 1 : 0
  location = google_cloud_run_v2_service.dc_web_service.location
  project  = google_cloud_run_v2_service.dc_web_service.project
  service  = google_cloud_run_v2_service.dc_web_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
