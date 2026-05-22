locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
  display_name_prefix = var.namespace != "" ? "(${var.namespace}) " : ""
}

resource "google_redis_instance" "redis_instance" {
  name                    = var.instance_name != "" ? "${local.name_prefix}${var.instance_name}" : "${local.name_prefix}dc-redis-instance"
  memory_size_gb          = var.memory_size_gb
  tier                    = var.tier
  region                  = var.region
  location_id             = var.location_id
  alternative_location_id = var.alternative_location_id
  redis_version           = "REDIS_6_X"
  display_name            = "${local.display_name_prefix}Data Commons Redis Instance"
  reserved_ip_range       = null
  replica_count           = var.replica_count
  authorized_network      = var.vpc_network_id
  connect_mode            = "DIRECT_PEERING"
}

resource "google_vpc_access_connector" "connector" {
  count         = var.enable_connector ? 1 : 0
  name          = "${local.name_prefix}dc-vpc-conn"

  region        = var.region
  network       = var.vpc_network_id
  ip_cidr_range = var.vpc_connector_cidr
  min_instances = 2
  max_instances = 10
}
