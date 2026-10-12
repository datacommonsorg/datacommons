locals {
  # Parse Spanner version retention period into seconds
  retention_raw = var.version_retention_period
  retention_seconds = (
    endswith(local.retention_raw, "d") ? tonumber(trimsuffix(local.retention_raw, "d")) * 86400 :
    endswith(local.retention_raw, "h") ? tonumber(trimsuffix(local.retention_raw, "h")) * 3600 :
    tonumber(trimsuffix(local.retention_raw, "s"))
  )
  warn_50pct_threshold_sec  = floor(local.retention_seconds * 0.50)
  warn_90pct_threshold_sec  = floor(local.retention_seconds * 0.90)
  crit_100pct_threshold_sec = local.retention_seconds

  instance_prefix = var.instance_name != "" ? "${var.instance_name} - " : ""
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
    display_name = "Lock acquired in Ingestion Helper but not released within ${floor(local.warn_50pct_threshold_sec / 3600)} hours"
    condition_matched_log {
      filter = <<-EOT
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="${var.service_name}"
        AND (jsonPayload.event="INGESTION_LOCK_ACQUIRED" OR textPayload:"INGESTION_LOCK_ACQUIRED")
      EOT
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "${local.retention_seconds}s"
  }

  documentation {
    content = <<-EOT
      ## ⚠️ WARNING: Ingestion Lock Held > 50% of Spanner Version Retention
      The global ingestion lock in Spanner database `${var.database_id}` has been held for over **${floor(local.warn_50pct_threshold_sec / 3600)} hours** (50% of the Spanner version retention period `${var.version_retention_period}`).
      
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
    display_name = "Warning: Lock held for ${floor(local.warn_90pct_threshold_sec / 3600)} hours (approaching retention expiration)"
    condition_matched_log {
      filter = <<-EOT
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="${var.service_name}"
        AND (jsonPayload.event="INGESTION_LOCK_ACQUIRED" OR textPayload:"INGESTION_LOCK_ACQUIRED")
      EOT
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "1800s"
    }
    auto_close = "${local.retention_seconds}s"
  }

  documentation {
    content = <<-EOT
      ## ⚠️ WARNING: Ingestion Lock Approaching 90% of Spanner Retention Limit
      The ingestion lock in Spanner database `${var.database_id}` has been held for over **${floor(local.warn_90pct_threshold_sec / 3600)} hours** (90% of `${var.version_retention_period}`).
      
      ### Imminent Danger:
      **PITR rollback window closes in ${floor((local.retention_seconds - local.warn_90pct_threshold_sec) / 3600)} hours!**
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
    display_name = "Critical: Lock held for >= ${floor(local.crit_100pct_threshold_sec / 3600)} hours (Spanner retention horizon breached)"
    condition_matched_log {
      filter = <<-EOT
        resource.type="cloud_run_revision"
        AND resource.labels.service_name="${var.service_name}"
        AND (jsonPayload.event="INGESTION_LOCK_ACQUIRED" OR textPayload:"INGESTION_LOCK_ACQUIRED")
      EOT
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "900s"
    }
    auto_close = "${local.retention_seconds * 2}s"
  }

  documentation {
    content = <<-EOT
      ## 🚨 CRITICAL PROD ERROR: Spanner Version Retention Horizon Breached!
      The ingestion lock in Spanner database `${var.database_id}` has been held for over **${floor(local.crit_100pct_threshold_sec / 3600)} hours**, completely exceeding the configured Spanner version retention period (`${var.version_retention_period}`).
      
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
