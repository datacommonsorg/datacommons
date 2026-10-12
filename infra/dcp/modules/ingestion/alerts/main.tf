locals {
  # Parse Spanner version retention period into seconds (valid Spanner values: [1h, 7d])
  retention_raw = var.version_retention_period
  retention_seconds = (
    endswith(local.retention_raw, "d") ? tonumber(trimsuffix(local.retention_raw, "d")) * 86400 :
    endswith(local.retention_raw, "h") ? tonumber(trimsuffix(local.retention_raw, "h")) * 3600 :
    endswith(local.retention_raw, "m") ? tonumber(trimsuffix(local.retention_raw, "m")) * 60 :
    tonumber(trimsuffix(local.retention_raw, "s"))
  )
  warn_50pct_threshold_sec  = floor(local.retention_seconds * 0.50)
  warn_90pct_threshold_sec  = floor(local.retention_seconds * 0.90)
  crit_100pct_threshold_sec = local.retention_seconds

  warn_50pct_display      = local.warn_50pct_threshold_sec >= 3600 ? "${floor(local.warn_50pct_threshold_sec / 3600)} hours" : "${floor(local.warn_50pct_threshold_sec / 60)} minutes"
  warn_90pct_display      = local.warn_90pct_threshold_sec >= 3600 ? "${floor(local.warn_90pct_threshold_sec / 3600)} hours" : "${floor(local.warn_90pct_threshold_sec / 60)} minutes"
  crit_100pct_display     = local.crit_100pct_threshold_sec >= 3600 ? "${floor(local.crit_100pct_threshold_sec / 3600)} hours" : "${floor(local.crit_100pct_threshold_sec / 60)} minutes"
  remaining_10pct_display = (local.retention_seconds - local.warn_90pct_threshold_sec) >= 3600 ? "${floor((local.retention_seconds - local.warn_90pct_threshold_sec) / 3600)} hours" : "${floor((local.retention_seconds - local.warn_90pct_threshold_sec) / 60)} minutes"

  instance_prefix   = var.instance_name != "" ? "${var.instance_name} - " : ""
  clean_name_prefix = var.instance_name != "" ? "${replace(lower(var.instance_name), "_", "-")}-" : ""

  # Cloud Monitoring requires autoClose to be between 30 minutes (1800s) and 168 hours (604800s)
  auto_close_seconds      = min(max(local.retention_seconds, 1800), 604800)
  auto_close_crit_seconds = min(max(local.retention_seconds * 2, 1800), 604800)
}

# ==============================================================================
# Periodic Lock Status Prober (Cloud Scheduler)
# ==============================================================================

resource "google_cloud_scheduler_job" "lock_status_prober" {
  count       = var.enable_lock_status_scheduler ? 1 : 0
  name        = "${local.clean_name_prefix}dc-lock-status-probe"
  project     = var.project_id
  region      = var.region
  description = "Periodically pings Ingestion Helper /database/lock/status to verify Spanner retention SLA"
  schedule    = var.lock_status_ping_schedule
  time_zone   = "UTC"

  http_target {
    http_method = "GET"
    uri         = "${var.helper_url}/database/lock/status"

    oidc_token {
      service_account_email = var.scheduler_service_account_email
    }
  }
}

# ==============================================================================
# Ingestion Lock Duration Alerts (Spanner Retention Protection)
# ==============================================================================

resource "google_monitoring_alert_policy" "ingestion_lock_approaching_retention_warning_50pct" {
  count        = var.enable_alert_50pct ? 1 : 0
  display_name = "${local.instance_prefix}⚠️ WARNING: Ingestion Lock Held > 50% of Spanner Retention"
  project      = var.project_id
  combiner     = "OR"
  severity     = "WARNING"

  conditions {
    display_name = "Ingestion lock held >= 50% of retention horizon (${local.warn_50pct_display})"
    condition_matched_log {
      filter = <<-EOT
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="${var.service_name}"
        AND (jsonPayload.event="INGESTION_LOCK_HELD_50PCT_WARNING" OR textPayload:"INGESTION_LOCK_HELD_50PCT_WARNING")
      EOT
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "${local.auto_close_seconds}s"
  }

  documentation {
    content   = <<-EOT
      ## ⚠️ WARNING: Ingestion Lock Held > 50% of Spanner Version Retention
      The global ingestion lock in Spanner database `${var.database_id}` has been held for over **${local.warn_50pct_display}** (50% of the Spanner version retention period `${var.version_retention_period}`).
      
      The running ingestion is approaching the Spanner retention window.
    EOT
    mime_type = "text/markdown"
  }

  notification_channels = var.notification_channels
}

resource "google_monitoring_alert_policy" "ingestion_lock_approaching_retention_warning_90pct" {
  count        = var.enable_alert_90pct ? 1 : 0
  display_name = "${local.instance_prefix}⚠️ WARNING: Ingestion Lock Held > 90% of Spanner Retention"
  project      = var.project_id
  combiner     = "OR"
  severity     = "WARNING"

  conditions {
    display_name = "Ingestion lock held >= 90% of retention horizon (${local.warn_90pct_display})"
    condition_matched_log {
      filter = <<-EOT
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="${var.service_name}"
        AND (jsonPayload.event="INGESTION_LOCK_HELD_90PCT_WARNING" OR textPayload:"INGESTION_LOCK_HELD_90PCT_WARNING")
      EOT
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "1800s"
    }
    auto_close = "${local.auto_close_seconds}s"
  }

  documentation {
    content   = <<-EOT
      ## ⚠️ WARNING: Ingestion Lock Approaching 90% of Spanner Retention Limit
      The ingestion lock in Spanner database `${var.database_id}` has been held for over **${local.warn_90pct_display}** (90% of `${var.version_retention_period}`).
      
      The ingestion is dangerously close to exceeding the configured retention window (${local.remaining_10pct_display} remaining).
    EOT
    mime_type = "text/markdown"
  }

  notification_channels = var.notification_channels
}

resource "google_monitoring_alert_policy" "ingestion_lock_breached_retention_critical" {
  count        = var.enable_alert_100pct ? 1 : 0
  display_name = "${local.instance_prefix}🚨 CRITICAL: Ingestion Lock Exceeded 100% of Spanner Retention"
  project      = var.project_id
  combiner     = "OR"
  severity     = "CRITICAL"

  conditions {
    display_name = "Ingestion lock held >= 100% of retention horizon (${local.crit_100pct_display})"
    condition_matched_log {
      filter = <<-EOT
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="${var.service_name}"
        AND (jsonPayload.event="INGESTION_LOCK_HELD_100PCT_CRITICAL" OR textPayload:"INGESTION_LOCK_HELD_100PCT_CRITICAL")
      EOT
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "900s"
    }
    auto_close = "${local.auto_close_crit_seconds}s"
  }

  documentation {
    content   = <<-EOT
      ## 🚨 CRITICAL: Spanner Version Retention Horizon Exceeded!
      The ingestion lock in Spanner database `${var.database_id}` has been held for over **${local.crit_100pct_display}**, exceeding the configured Spanner version retention period (`${var.version_retention_period}`).
      
      Queries will serve data at the latest timestamp, which may introduce data integrity issues while this uncommitted or in-flight ingestion remains unresolved.
    EOT
    mime_type = "text/markdown"
  }

  notification_channels = var.notification_channels
}
