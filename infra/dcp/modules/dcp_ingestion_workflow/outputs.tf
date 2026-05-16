output "ingestion_orchestrator_id" {
  value = var.deploy ? google_workflows_workflow.ingestion_orchestrator[0].id : null
}

output "ingestion_orchestrator_name" {
  value = var.deploy ? google_workflows_workflow.ingestion_orchestrator[0].name : null
}

