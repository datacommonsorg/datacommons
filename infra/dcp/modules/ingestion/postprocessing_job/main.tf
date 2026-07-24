locals {
  name_prefix = var.instance_name != "" ? "${var.instance_name}-" : ""
}

resource "google_service_account" "postprocessing_sa" {
  account_id   = "${local.name_prefix}dc-ing-pst-sa"
  display_name = "Data Commons Ingestion Postprocessing SA"
}

resource "google_cloud_run_v2_job" "dc_postprocessing_job" {
  name                = "${local.name_prefix}dc-ingestion-postprocessing-job"
  location            = var.region
  deletion_protection = var.stateless_deletion_protection

  template {
    template {
      containers {
        image = var.image
        resources {
          limits = {
            cpu    = var.cpu
            memory = var.memory
          }
        }

        dynamic "env" {
          for_each = var.env_vars
          content {
            name  = env.value.name
            value = env.value.value
          }
        }

        env {
          name  = "SPANNER_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "SPANNER_INSTANCE_ID"
          value = var.spanner_instance_id
        }
        env {
          name  = "SPANNER_DATABASE_ID"
          value = var.spanner_database_id
        }
        env {
          name  = "SPANNER_GRAPH_DATABASE_ID"
          value = var.spanner_database_id
        }
        env {
          name  = "BQ_SPANNER_CONN_ID"
          value = var.bigquery_connection_id
        }
        env {
          name  = "LOCATION"
          value = var.region
        }
        env {
          name  = "ENABLE_EMBEDDINGS"
          value = var.enable_spanner_embeddings ? "true" : "false"
        }
      }

      dynamic "vpc_access" {
        for_each = var.vpc_connector_id != null && var.vpc_connector_id != "" ? [1] : []
        content {
          connector = var.vpc_connector_id
          egress    = "PRIVATE_RANGES_ONLY"
        }
      }

      max_retries     = 0
      timeout         = var.timeout
      service_account = google_service_account.postprocessing_sa.email
    }
  }
}

# Encapsulated Spanner Database & BigQuery IAM Roles for Postprocessing SA
resource "google_project_iam_member" "postprocessing_spanner" {
  count   = var.use_spanner ? 1 : 0
  project = var.project_id
  role    = "roles/spanner.databaseUser"
  member  = "serviceAccount:${google_service_account.postprocessing_sa.email}"
}

resource "google_project_iam_member" "postprocessing_bq_data_editor" {
  count   = var.enable_bigquery_postprocessing ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.postprocessing_sa.email}"
}

resource "google_project_iam_member" "postprocessing_bq_job_user" {
  count   = var.enable_bigquery_postprocessing ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.postprocessing_sa.email}"
}

resource "google_project_iam_member" "postprocessing_bq_connection_user" {
  count   = var.enable_bigquery_postprocessing && var.enable_bigquery_connection ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.connectionUser"
  member  = "serviceAccount:${google_service_account.postprocessing_sa.email}"
}
