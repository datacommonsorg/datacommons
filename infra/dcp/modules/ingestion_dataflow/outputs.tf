output "ingestion_runner_email" {
  value = var.deploy ? google_service_account.ingestion_runner[0].email : null
}

output "ingestion_runner_id" {
  value = var.deploy ? google_service_account.ingestion_runner[0].id : null
}

output "orchestrator_email" {
  value = var.deploy ? google_service_account.ingestion_orchestrator[0].email : null
}

output "orchestrator_id" {
  value = var.deploy ? google_service_account.ingestion_orchestrator[0].id : null
}

