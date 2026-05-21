output "platform_service_url" {
  value = var.platform_service_config.enable ? module.platform_service[0].service_url : null
}

output "spanner_instance_id" {
  value = module.spanner.spanner_instance_id
}

output "spanner_database_id" {
  value = module.spanner.spanner_database_id
}

output "datacommons_service_url" {
  value = module.datacommons_service[0].service_url
}

output "datacommons_service_name" {
  value = module.datacommons_service[0].service_name
}

output "ingestion_workflow_id" {
  description = "ID of the ingestion Cloud Workflows orchestrator"
  value       = var.platform_service_config.enable && var.ingestion_config.deploy_workflow ? module.ingestion_workflow[0].ingestion_orchestrator_id : null
}

output "ingestion_bucket_url" {
  description = "GCS URL pointing directly to the dynamically provisioned bucket for your input graph MCF files"
  value       = var.platform_service_config.enable && var.ingestion_config.deploy_workflow ? module.storage.pipeline_bucket_url : null
}

output "ingestion_workflow_name" {
  description = "Name of the ingestion Cloud Workflows orchestrator"
  value       = var.platform_service_config.enable && var.ingestion_config.deploy_workflow ? module.ingestion_workflow[0].ingestion_orchestrator_name : null
}

output "ingestion_service_uri" {
  description = "URI of the ingestion support Cloud Run service"
  value       = var.platform_service_config.enable && var.ingestion_config.deploy_workflow ? module.ingestion_service[0].ingestion_helper_uri : null
}

output "ingestion_prep_job_name" {
  description = "Name of the data ingestion pre-processing job"
  value       = module.ingestion_prep_job[0].job_name
}

output "ingestion_orchestrator_service_account_email" {
  description = "Email of the orchestrator service account used by CLI and Workflows"
  value       = var.platform_service_config.enable && var.ingestion_config.deploy_workflow ? module.ingestion_dataflow[0].orchestrator_email : null
}

output "ingestion_prep_bucket_name" {
  description = "Name of the GCS bucket used for data ingestion pre-processing"
  value       = module.storage.prep_bucket_name
}
