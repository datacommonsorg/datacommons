locals {
  name_prefix           = var.namespace != "" ? "${var.namespace}-" : ""
  artifacts_bucket_name = var.artifacts_bucket_name != "" ? var.artifacts_bucket_name : "${local.name_prefix}dc-artifacts-${var.project_id}"
}

resource "google_storage_bucket" "artifacts_bucket" {
  count                       = var.create_artifacts_bucket ? 1 : 0
  name                        = local.artifacts_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = !var.stateful_deletion_protection

  depends_on = [var.foundation_dependency]
}

