# State migrations for resources within modules/stack.
#
# Guideline for contributors:
# When refactoring changes a resource's Terraform state address (renaming,
# moving between modules, or shifting count/for_each to callers), add a moved
# block below under a version header to preserve live state across upgrades.
# Group blocks by the target release version where the address changed.

# -----------------------------------------------------------------------------
# Upgrades from <= 1.1.6 (introduced in 1.1.7)
#
# Module "ingestion_helper_service" moved count to the caller module, changing
# child resource addresses from unindexed to indexed (`module.ingestion_helper_service[0]`).
# -----------------------------------------------------------------------------

moved {
  from = module.ingestion_helper_service.google_service_account.helper_sa[0]
  to   = module.ingestion_helper_service[0].google_service_account.helper_sa
}

moved {
  from = module.ingestion_helper_service.google_cloud_run_v2_service.ingestion_helper[0]
  to   = module.ingestion_helper_service[0].google_cloud_run_v2_service.ingestion_helper
}

moved {
  from = module.ingestion_helper_service.google_spanner_database_iam_member.helper_spanner_user[0]
  to   = module.ingestion_helper_service[0].google_spanner_database_iam_member.helper_spanner_user
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
  from = module.ingestion_helper_service.google_secret_manager_secret_iam_member.helper_redis_auth_secret_accessor[0]
  to   = module.ingestion_helper_service[0].google_secret_manager_secret_iam_member.helper_redis_auth_secret_accessor[0]
}
