locals {
  name_prefix               = var.namespace != "" ? "${var.namespace}-" : ""
  should_run_postprocessing = var.enable_bigquery_postprocessing || var.enable_embeddings_generation
  clean_namespace_prefix    = var.namespace != "" ? "${replace(lower(var.namespace), "_", "-")}-" : ""
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
    project_id                     = var.project_id
    ingestion_helper_url           = var.ingestion_helper_url
    lock_acquisition_timeout       = var.lock_acquisition_timeout
    enable_embeddings_generation   = var.enable_embeddings_generation
    enable_bigquery_postprocessing = var.enable_bigquery_postprocessing
    ingestion_artifacts_path       = var.ingestion_artifacts_path
    dataflow_template_gcs_path     = var.dataflow_template_gcs_path
    dataflow_service_account_email = var.dataflow_service_account_email
    dataflow_ip_configuration      = var.dataflow_ip_configuration
    dataflow_subnetwork            = var.dataflow_subnetwork
    embeddings_timeout             = var.embeddings_timeout
    clean_namespace_prefix         = local.clean_namespace_prefix
    enable_redis_cache_clearing    = var.enable_redis_cache_clearing
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
