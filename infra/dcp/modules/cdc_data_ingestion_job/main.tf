locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
}

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

        env {
          name  = "GCS_BUCKET"
          value = var.bucket_name
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
          value = "gs://${var.bucket_name}/${var.gcs_data_bucket_input_folder}"
        }
      }
      vpc_access {
        connector = var.vpc_connector_id
        egress    = "PRIVATE_RANGES_ONLY"
      }
      max_retries     = 0
      timeout         = var.dc_data_job_timeout
      service_account = var.service_account_email
    }
  }
}

resource "null_resource" "run_db_init" {
  count = var.run_db_init ? 1 : 0

  depends_on = [google_cloud_run_v2_job.dc_data_job]

  triggers = {
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
