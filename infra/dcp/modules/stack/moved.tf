# =============================================================================
# STATE MIGRATIONS (moved.tf)
# =============================================================================
#
# These blocks ensure seamless state migration for existing DCP deployments
# without destroying and recreating resources.
#
# Modernization of ingestion_helper_service: shift from internal var.deploy
# to caller-level count in modules/stack/main.tf.
# =============================================================================

moved {
  from = module.ingestion_helper_service.google_service_account.helper_sa[0]
  to   = module.ingestion_helper_service[0].google_service_account.helper_sa
}

moved {
  from = module.ingestion_helper_service.google_cloud_run_v2_service.ingestion_helper[0]
  to   = module.ingestion_helper_service[0].google_cloud_run_v2_service.ingestion_helper
}

moved {
  from = module.ingestion_helper_service.google_storage_bucket_iam_member.helper_bucket_access[0]
  to   = module.ingestion_helper_service[0].google_storage_bucket_iam_member.helper_bucket_access
}

moved {
  from = module.ingestion_helper_service.google_project_iam_member.helper_dataflow_viewer[0]
  to   = module.ingestion_helper_service[0].google_project_iam_member.helper_dataflow_viewer
}

moved {
  from = module.ingestion_helper_service.google_spanner_database_iam_member.helper_spanner_user[0]
  to   = module.ingestion_helper_service[0].google_spanner_database_iam_member.helper_spanner_user[0]
}

moved {
  from = module.ingestion_helper_service.google_secret_manager_secret_iam_member.helper_redis_auth_secret_accessor[0]
  to   = module.ingestion_helper_service[0].google_secret_manager_secret_iam_member.helper_redis_auth_secret_accessor[0]
}
