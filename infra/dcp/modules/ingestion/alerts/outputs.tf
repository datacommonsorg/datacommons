output "warning_50pct_alert_policy_id" {
  description = "The ID of the 50% retention warning alert policy."
  value       = try(google_monitoring_alert_policy.ingestion_lock_approaching_retention_warning_50pct[0].id, null)
}

output "warning_90pct_alert_policy_id" {
  description = "The ID of the 90% retention warning alert policy."
  value       = try(google_monitoring_alert_policy.ingestion_lock_approaching_retention_warning_90pct[0].id, null)
}

output "critical_100pct_alert_policy_id" {
  description = "The ID of the 100% retention critical alert policy."
  value       = try(google_monitoring_alert_policy.ingestion_lock_breached_retention_critical[0].id, null)
}
