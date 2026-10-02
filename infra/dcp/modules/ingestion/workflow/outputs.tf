output "workflow_id" {
  value = var.deploy ? google_workflows_workflow.ingestion_orchestrator[0].id : null
}

output "workflow_name" {
  value = var.deploy ? google_workflows_workflow.ingestion_orchestrator[0].name : null
}

output "service_account_email" {
  value = var.deploy ? google_service_account.workflow_sa[0].email : null
}

output "ingestion_dataflow_template_gcs_path" {
  description = "GCS path to the ingestion Dataflow flex template specification deployed to the workflow"
  value       = var.deploy ? var.ingestion_dataflow_template_gcs_path : null
}

output "preprocessing_job_image" {
  description = "Container image URI for Cloud Batch preprocessing deployed to the workflow"
  value       = var.deploy ? var.preprocessing_config.image : null
}


