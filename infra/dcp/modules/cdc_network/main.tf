locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
}

resource "google_vpc_access_connector" "connector" {
  name          = "${local.name_prefix}vpc-conn"
  region        = var.region
  network       = var.vpc_network_name
  ip_cidr_range = var.vpc_connector_cidr
  min_instances = 2
  max_instances = 10
}
