variable "project_id" {
  description = "The GCP project ID where the alerts will be created."
  type        = string
}

variable "instance_name" {
  description = "The instance name prefix for alert display names."
  type        = string
  default     = ""
}

variable "database_id" {
  description = "The Spanner database ID being monitored."
  type        = string
}

variable "version_retention_period" {
  description = "The Spanner version retention period (e.g. '24h', '7d')."
  type        = string
}

variable "service_name" {
  description = "The Cloud Run service name of the Ingestion Helper."
  type        = string
}

variable "notification_channels" {
  description = "List of Cloud Monitoring notification channel IDs."
  type        = list(string)
  default     = []
}

variable "enable_alert_50pct" {
  description = "Enable the 50% retention window warning alert."
  type        = bool
  default     = true
}

variable "enable_alert_90pct" {
  description = "Enable the 90% retention window warning alert."
  type        = bool
  default     = true
}

variable "enable_alert_100pct" {
  description = "Enable the 100% retention horizon breach critical alert."
  type        = bool
  default     = true
}

variable "region" {
  description = "GCP region for regional resources such as Cloud Scheduler."
  type        = string
  default     = ""
}

variable "helper_url" {
  description = "Base URL of the Ingestion Helper Cloud Run service."
  type        = string
  default     = ""
}

variable "scheduler_service_account_email" {
  description = "Service account email used by Cloud Scheduler with roles/run.invoker to ping Ingestion Helper."
  type        = string
  default     = ""
}

variable "enable_lock_status_scheduler" {
  description = "Enable Cloud Scheduler job to periodically ping /database/lock/status. Default: false."
  type        = bool
  default     = false
}

variable "lock_status_ping_schedule" {
  description = "Cron schedule expression for the lock status probe job (e.g., '*/10 * * * *')."
  type        = string
  default     = "*/10 * * * *"
}
