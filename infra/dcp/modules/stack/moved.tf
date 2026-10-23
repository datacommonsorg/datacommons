# State migrations for resources within modules/stack.
#
# PR #303 moved `count = var.deploy ? 1 : 0` from individual resources inside
# `modules/ingestion/helper_service` up to the caller `module "ingestion_helper_service"`
# block in `modules/stack/main.tf`.
#
# These moved blocks preserve the existing Terraform state addresses across upgrades
# from DCP 1.1.6 to prevent destroy-and-recreate cycles on live resources.

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
