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
          value = var.spanner_config.instance_id
        }
        env {
          name  = "SPANNER_DATABASE_ID"
          value = var.spanner_config.database_id
        }
        env {
          name  = "SPANNER_GRAPH_DATABASE_ID"
          value = var.spanner_config.database_id
        }
        env {
          name  = "BQ_SPANNER_CONN_ID"
          value = var.spanner_config.bigquery_connection_id != null ? var.spanner_config.bigquery_connection_id : ""
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

      # Direct VPC Egress
      dynamic "vpc_access" {
        for_each = var.vpc_access != null ? [var.vpc_access] : []
        content {
          network_interfaces {
            network    = vpc_access.value.network_id
            subnetwork = vpc_access.value.subnet_id
            tags       = ["dcp-job"]
          }
          egress = vpc_access.value.vpc_egress_mode
        }
      }

      max_retries     = 0
      timeout         = var.timeout
      service_account = google_service_account.postprocessing_sa.email
    }
  }
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

resource "google_spanner_database_iam_member" "postprocessing_spanner_user" {
  project  = var.project_id
  instance = var.spanner_config.instance_id
  database = var.spanner_config.database_id
  role     = "roles/spanner.databaseUser"
  member   = "serviceAccount:${google_service_account.postprocessing_sa.email}"
}

# When the postprocessing job runs BigQuery federated queries (EXTERNAL_QUERY) against Spanner
# with parallel reads enabled, BigQuery accesses Spanner using the caller's identity (postprocessing_sa)
# and checks metadata on the parent Spanner instance (spanner.instances.get). Because database-level
# IAM bindings do not inherit upward to the instance, removing this binding causes BigQuery
# postprocessing steps to fail with "Permission Denied" on projects/{project}/instances/{instance}.
# Granting roles/spanner.viewer on the instance provides the required instance metadata access
# without granting table read access to other databases on a shared Spanner instance.
resource "google_spanner_instance_iam_member" "postprocessing_spanner_instance_viewer" {
  count    = var.enable_bigquery_postprocessing && var.spanner_config.enable_bigquery_connection ? 1 : 0
  project  = var.project_id
  instance = var.spanner_config.instance_id
  role     = "roles/spanner.viewer"
  member   = "serviceAccount:${google_service_account.postprocessing_sa.email}"
}

resource "google_bigquery_connection_iam_member" "postprocessing_bq_connection_user" {
  count         = var.enable_bigquery_postprocessing && var.spanner_config.enable_bigquery_connection ? 1 : 0
  project       = var.project_id
  location      = var.region
  connection_id = var.spanner_config.bigquery_connection_id
  role          = "roles/bigquery.connectionUser"
  member        = "serviceAccount:${google_service_account.postprocessing_sa.email}"
}
