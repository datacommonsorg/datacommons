locals {
  name_prefix                = var.instance_name != "" ? "${var.instance_name}-" : ""
  should_run_postprocessing  = var.enable_bigquery_postprocessing || var.enable_embeddings_generation
  clean_instance_name_prefix = var.instance_name != "" ? "${replace(lower(var.instance_name), "_", "-")}-" : ""
}

resource "google_service_account" "workflow_sa" {
  count        = var.deploy ? 1 : 0
  account_id   = "${local.name_prefix}dc-ing-wf-sa"
  display_name = "Data Commons Ingestion Workflow SA"
}

resource "google_workflows_workflow" "ingestion_orchestrator" {
  count               = var.deploy ? 1 : 0
  name                = "${local.name_prefix}dc-ingestion-workflow"
  region              = var.region
  description         = "Triggers the Dataflow Flex Template Graph Ingestion Pipeline with runtime parameters"
  service_account     = google_service_account.workflow_sa[0].email
  deletion_protection = var.stateless_deletion_protection

  source_contents = templatefile("${path.module}/workflow.yaml", {
    project_id                           = var.project_id
    region                               = var.region
    ingestion_helper_url                 = var.ingestion_helper_url
    lock_acquisition_timeout             = var.lock_acquisition_timeout
    enable_embeddings_generation         = var.enable_embeddings_generation
    enable_bigquery_postprocessing       = var.enable_bigquery_postprocessing
    artifacts_bucket_name                = var.artifacts_bucket_name
    ingestion_artifacts_path             = var.ingestion_artifacts_path
    ingestion_input_path                 = var.ingestion_input_path
    vpc_network                          = var.vpc_network
    ingestion_dataflow_template_gcs_path = var.ingestion_dataflow_template_gcs_path
    rollback_dataflow_template_gcs_path  = var.rollback_dataflow_template_gcs_path
    dataflow_service_account_email       = var.dataflow_service_account_email
    worker_ip_configuration              = var.worker_ip_configuration
    worker_subnetwork                    = var.worker_subnetwork
    embeddings_timeout                   = var.embeddings_timeout
    clean_instance_name_prefix           = local.clean_instance_name_prefix
    enable_redis_cache_clearing          = var.enable_redis_cache_clearing
    preprocessing_job_image              = var.preprocessing_config.image
    preprocessing_cpu                    = var.preprocessing_config.cpu
    preprocessing_memory                 = var.preprocessing_config.memory
    preprocessing_timeout                = var.preprocessing_config.timeout
    preprocessing_service_account_email  = var.preprocessing_config.service_account_email
    spanner_instance_id                  = var.spanner_instance_id
    spanner_database_id                  = var.spanner_database_id
    dc_api_key_secret_version            = var.preprocessing_config.dc_api_key_secret_version
    postprocessing_job_name              = var.postprocessing_job_name
    dataflow_max_workers                 = var.dataflow_max_workers
    dataflow_num_workers                 = var.dataflow_num_workers
    dataflow_worker_machine_type         = var.dataflow_worker_machine_type
    enable_datacommons_services_restart  = var.enable_datacommons_services_restart
    datacommons_services_name            = var.datacommons_services_name
  })
}

resource "google_service_account_iam_member" "workflow_act_as_dataflow_sa" {
  count              = var.deploy ? 1 : 0
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.dataflow_service_account_email}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.workflow_sa[0].email}"
}

resource "google_cloud_run_v2_service_iam_member" "helper_invoker" {
  count    = var.deploy && var.ingestion_helper_service_name != "" ? 1 : 0
  location = var.region
  name     = var.ingestion_helper_service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.workflow_sa[0].email}"
}
