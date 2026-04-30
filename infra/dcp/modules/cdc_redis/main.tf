locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
  display_name_prefix = var.namespace != "" ? "(${var.namespace}) " : ""
}

resource "google_redis_instance" "redis_instance" {
  name                    = "${local.name_prefix}${var.redis_instance_name}"
  memory_size_gb          = var.redis_memory_size_gb
  tier                    = var.redis_tier
  region                  = var.region
  location_id             = var.redis_location_id
  alternative_location_id = var.redis_alternative_location_id
  redis_version           = "REDIS_6_X"
  display_name            = "${local.display_name_prefix}Data Commons Redis Instance"
  reserved_ip_range       = null
  replica_count           = var.redis_replica_count
  authorized_network      = var.vpc_network_id
  connect_mode            = "DIRECT_PEERING"
}
