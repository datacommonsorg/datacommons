locals {
  name_prefix         = var.instance_name != "" ? "${var.instance_name}-" : ""
  display_name_prefix = var.instance_name != "" ? "(${var.instance_name}) " : ""
}

resource "google_redis_instance" "redis_instance" {
  name                    = var.redis_instance_name != "" ? "${local.name_prefix}${var.redis_instance_name}" : "${local.name_prefix}dc-redis-instance"
  memory_size_gb          = var.memory_size_gb
  tier                    = var.tier
  region                  = var.region
  location_id             = var.location_id
  alternative_location_id = var.tier == "BASIC" ? null : var.alternative_location_id
  redis_version           = "REDIS_6_X"
  display_name            = "${local.display_name_prefix}Data Commons Redis Instance"
  reserved_ip_range       = null
  replica_count           = var.tier == "BASIC" ? 0 : var.replica_count
  authorized_network      = var.vpc_network_id
  connect_mode            = "DIRECT_PEERING"
  auth_enabled            = var.enable_auth
  transit_encryption_mode = var.enable_tls ? "SERVER_AUTHENTICATION" : "DISABLED"
}

resource "google_secret_manager_secret" "redis_auth" {
  count     = var.enable_auth ? 1 : 0
  secret_id = "${local.name_prefix}dc-redis-auth"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "redis_auth_version" {
  count       = var.enable_auth ? 1 : 0
  secret      = google_secret_manager_secret.redis_auth[0].id
  secret_data = google_redis_instance.redis_instance.auth_string
}
