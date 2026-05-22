output "service_account_email" {
  value = var.deploy ? google_service_account.dataflow_sa[0].email : null
}

output "service_account_id" {
  value = var.deploy ? google_service_account.dataflow_sa[0].id : null
}

