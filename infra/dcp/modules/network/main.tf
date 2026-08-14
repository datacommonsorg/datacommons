locals {
  name_prefix = var.instance_name != "" ? "${var.instance_name}-" : ""

  effective_network_id = var.enable ? (
    var.create_vpc ? (length(google_compute_network.vpc) > 0 ? google_compute_network.vpc[0].id : "") : var.existing_network_id
  ) : null

  effective_network_name = var.enable ? (
    var.create_vpc ? (length(google_compute_network.vpc) > 0 ? google_compute_network.vpc[0].name : "") : var.network_name
  ) : null

  effective_subnet_id = var.enable ? (
    var.create_vpc ? (length(google_compute_subnetwork.subnet) > 0 ? google_compute_subnetwork.subnet[0].id : "") : var.existing_subnet_id
  ) : null

  effective_subnet_url = var.enable ? (
    var.create_vpc ? (length(google_compute_subnetwork.subnet) > 0 ? google_compute_subnetwork.subnet[0].self_link : "") : var.existing_subnet_id
  ) : null
}

# =============================================================================
# 1. Custom VPC Network
# =============================================================================
resource "google_compute_network" "vpc" {
  count                   = var.enable && var.create_vpc ? 1 : 0
  name                    = var.network_name != "" ? "${local.name_prefix}${var.network_name}" : "${local.name_prefix}dc-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id
}

# =============================================================================
# 2. Private Subnet with Private Google Access (PGA)
# =============================================================================
resource "google_compute_subnetwork" "subnet" {
  count                    = var.enable && var.create_vpc ? 1 : 0
  name                     = "${local.name_prefix}dc-subnet"
  ip_cidr_range            = var.subnet_cidr
  region                   = var.region
  network                  = google_compute_network.vpc[0].id
  private_ip_google_access = true # Ensures internal routing to Spanner, BigQuery, GCS without public IPs
  project                  = var.project_id
}

# =============================================================================
# 3. Cloud Router & Cloud NAT for Secure Outbound Egress
# =============================================================================
resource "google_compute_router" "router" {
  count   = var.enable && var.create_vpc && var.enable_cloud_nat ? 1 : 0
  name    = "${local.name_prefix}dc-router"
  region  = var.region
  network = google_compute_network.vpc[0].id
  project = var.project_id
}

resource "google_compute_router_nat" "nat" {
  count                              = var.enable && var.create_vpc && var.enable_cloud_nat ? 1 : 0
  name                               = "${local.name_prefix}dc-nat"
  router                             = google_compute_router.router[0].name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  project                            = var.project_id

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
