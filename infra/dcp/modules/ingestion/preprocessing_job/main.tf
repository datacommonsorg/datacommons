locals {
  name_prefix         = var.namespace != "" ? "${var.namespace}-" : ""
  tmp_disk_mount_path = "/mnt/preprocessing-tmp"
  tmp_disk_size       = var.tmp_disk_size == null ? "" : trimspace(var.tmp_disk_size)
  tmp_disk_enabled    = local.tmp_disk_size != ""
}

resource "google_service_account" "preprocessing_sa" {
  account_id   = "${local.name_prefix}dc-ing-pre-sa"
  display_name = "Data Commons Ingestion Preprocessing SA"
}

resource "google_cloud_run_v2_job" "dc_data_job" {
  name                = "${local.name_prefix}dc-ingestion-preprocessing-job"
  location            = var.region
  launch_stage         = local.tmp_disk_enabled ? "BETA" : null
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

        dynamic "volume_mounts" {
          for_each = local.tmp_disk_enabled ? [1] : []
          content {
            name       = "preprocessing-tmp"
            mount_path = local.tmp_disk_mount_path
          }
        }

        dynamic "env" {
          for_each = var.env_vars
          content {
            name  = env.value.name
            value = env.value.value
          }
        }

        dynamic "env" {
          for_each = var.secret_env_vars
          content {
            name = env.value.name
            value_source {
              secret_key_ref {
                secret  = env.value.secret
                version = env.value.version
              }
            }
          }
        }

        dynamic "env" {
          for_each = local.tmp_disk_enabled ? [1] : []
          content {
            name  = "TMPDIR"
            value = local.tmp_disk_mount_path
          }
        }

        env {
          name  = "GCS_BUCKET"
          value = var.bucket_name
        }
        env {
          name  = "GCS_INPUT_FOLDER"
          value = var.input_path
        }
        env {
          name  = "GCS_OUTPUT_FOLDER"
          value = var.ingestion_artifacts_path
        }
        env {
          name  = "INPUT_DIR"
          value = "gs://${var.bucket_name}/${var.input_path}"
        }
        env {
          name  = "ENABLE_SPANNER_EMBEDDINGS"
          value = var.enable_spanner_embeddings ? "true" : "false"
        }

      }
      dynamic "volumes" {
        for_each = local.tmp_disk_enabled ? [local.tmp_disk_size] : []
        content {
          name = "preprocessing-tmp"
          empty_dir {
            medium     = "DISK"
            size_limit = volumes.value
          }
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
      service_account = google_service_account.preprocessing_sa.email
    }
  }
}

resource "null_resource" "run_db_init" {
  count = var.run_database_init ? 1 : 0

  depends_on = [google_cloud_run_v2_job.dc_data_job]

  triggers = {
    job_image = var.image
  }

  provisioner "local-exec" {
    command = <<EOT
      gcloud run jobs execute ${local.name_prefix}dc-ingestion-preprocessing-job \
        --update-env-vars DATA_RUN_MODE=schemaupdate \
        --region=${var.region} \
        --project=${var.project_id} \
        --wait
EOT
  }
}

resource "google_secret_manager_secret_iam_member" "preprocessing_api_key_accessor" {
  project   = var.project_id
  secret_id = var.dc_api_key_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.preprocessing_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "preprocessing_maps_key_accessor" {
  project   = var.project_id
  secret_id = var.maps_api_key_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.preprocessing_sa.email}"
}
