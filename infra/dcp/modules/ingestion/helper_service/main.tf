locals {
  name_prefix = var.instance_name != "" ? "${var.instance_name}-" : ""
}

resource "google_service_account" "helper_sa" {
  count        = var.deploy ? 1 : 0
  account_id   = "${local.name_prefix}dc-ing-hlp-sa"
  display_name = "Data Commons Ingestion Helper SA"
}

resource "google_cloud_run_v2_service" "ingestion_helper" {
  count               = var.deploy ? 1 : 0
  name                = "${local.name_prefix}dc-ingestion-helper"
  location            = var.region
  deletion_protection = var.stateless_deletion_protection

  # TODO: Restrict ingress to INGRESS_TRAFFIC_INTERNAL_ONLY once datacommons-admin CLI
  # supports triggering seed-db and init-db via Cloud Workflows/Jobs or VPC bastion proxies.
  # Note: IAM authentication (roles/run.invoker) is still strictly enforced by Cloud Run.
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    timeout = "1800s"
    containers {
      image = var.image

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "FORCE_RESTART"
        value = var.skip_container_restarts ? "" : timestamp()
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
        name  = "LOCATION"
        value = var.region
      }
      env {
        name  = "GCS_BUCKET_ID"
        value = var.ingestion_bucket_name
      }
      env {
        name  = "GCS_OUTPUT_PREFIX"
        value = var.ingestion_artifacts_path
      }
      env {
        name  = "IS_BASE_DC"
        value = "false"
      }
      env {
        name  = "ENABLE_EMBEDDINGS"
        value = var.enable_embeddings_generation
      }
      env {
        name  = "REDIS_HOST"
        value = var.redis_host
      }
      env {
        name  = "REDIS_PORT"
        value = var.redis_port
      }
      env {
        name  = "ENABLE_UNIQUE_INGESTION_RUNS"
        value = "true"
        # Temporary variable to control changes to the ingestion history table. To be deleted after migration complete.
      }
    }

    # Direct VPC Egress
    dynamic "vpc_access" {
      for_each = var.subnet_id != null && var.subnet_id != "" ? [1] : []
      content {
        network_interfaces {
          network    = var.network_id
          subnetwork = var.subnet_id
          tags       = ["dcp-service"]
        }
        egress = var.vpc_egress_mode
      }
    }

    service_account = google_service_account.helper_sa[0].email
  }
}

resource "google_project_iam_member" "helper_spanner_user" {
  count   = var.deploy && var.use_spanner ? 1 : 0
  project = var.project_id
  role    = "roles/spanner.databaseUser"
  member  = "serviceAccount:${google_service_account.helper_sa[0].email}"
}


resource "google_storage_bucket_iam_member" "helper_bucket_access" {
  count  = var.deploy ? 1 : 0
  bucket = var.ingestion_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.helper_sa[0].email}"
}

resource "google_project_iam_member" "helper_dataflow_viewer" {
  count   = var.deploy ? 1 : 0
  project = var.project_id
  role    = "roles/dataflow.viewer"
  member  = "serviceAccount:${google_service_account.helper_sa[0].email}"
}





