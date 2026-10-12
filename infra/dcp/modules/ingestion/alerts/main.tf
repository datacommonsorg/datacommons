locals {
  # Parse Spanner version retention period into seconds (valid Spanner values: [1h, 7d])
  retention_raw = var.version_retention_period
  retention_seconds = (
    endswith(local.retention_raw, "d") ? tonumber(trimsuffix(local.retention_raw, "d")) * 86400 :
    tonumber(trimsuffix(local.retention_raw, "h")) * 3600
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
  auto_close_seconds      = max(local.retention_seconds, 1800)
  auto_close_crit_seconds = max(local.retention_seconds * 2, 1800)
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
      
      ### Impact:
      If this ingestion fails after the Spanner retention window closes, **Point-in-Time Recovery (PITR) rollback will fail** because Spanner will have purged the pre-ingestion snapshot timestamp `t_pre_timestamp`.
      
      ### Recommended Action:
      1. Check the active workflow execution and Dataflow job progress.
      2. If the Dataflow pipeline or postprocessing job is hung, consider cancelling it before the retention window expires so PITR rollback can still succeed.
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
      
      ### Imminent Danger:
      **PITR rollback window closes in ${local.remaining_10pct_display}!**
      Once the retention period passes, Spanner garbage-collection permanently deletes past data versions. Any subsequent rollback attempt will throw an out-of-range timestamp error, leaving the database partially written and corrupt.
      
      ### Recommended Action:
      Inspect the running ingestion immediately. If progress is stalled, abort the workflow to trigger automatic PITR rollback before the remaining 10% window expires.
    EOT
    mime_type = "text/markdown"
  }

  notification_channels = var.notification_channels
}

resource "google_monitoring_alert_policy" "ingestion_lock_breached_retention_critical" {
  count        = var.enable_alert_100pct ? 1 : 0
  display_name = "${local.instance_prefix}🚨 CRITICAL: Ingestion Lock Exceeded 100% of Spanner Retention (PITR Invalidated)"
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
      ## 🚨 CRITICAL PROD ERROR: Spanner Version Retention Horizon Breached!
      The ingestion lock in Spanner database `${var.database_id}` has been held for over **${local.crit_100pct_display}**, completely exceeding the configured Spanner version retention period (`${var.version_retention_period}`).
      
      ### Outage & Data Corruption Risk:
      - **Point-in-Time Recovery (PITR) is now BROKEN**: The pre-ingestion snapshot timestamp `t_pre_timestamp` has been permanently purged by Spanner's compaction garbage collector.
      - **Automatic rollback will FAIL**: If the Dataflow pipeline fails or is cancelled now, the rollback job will fail with `SpannerException: Out of range timestamp: Earliest possible read timestamp is...`.
      - **Database is in an unrecoverable in-flight state**: The database cannot be automatically restored via PITR.
      
      ### Immediate Action Required:
      1. Contact database on-call immediately.
      2. Do NOT blindly cancel the Dataflow job if it is still writing healthy data, as cancellation rollback will fail.
      3. If the pipeline has failed or corrupted data, prepare to restore from an external Spanner backup.
    EOT
    mime_type = "text/markdown"
  }

  notification_channels = var.notification_channels
}
