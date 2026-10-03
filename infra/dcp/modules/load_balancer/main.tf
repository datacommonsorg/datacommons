locals {
  name_prefix = var.instance_name != "" ? "${var.instance_name}-" : ""
}

# =============================================================================
# 1. Static Global External IP Address (Anycast)
# =============================================================================
resource "google_compute_global_address" "lb_ip" {
  name        = "${local.name_prefix}dc-lb-ip"
  project     = var.project_id
  description = "Global Anycast IP for Data Commons Serving Load Balancer"
}

# =============================================================================
# 2. Serverless Network Endpoint Group (NEG)
# =============================================================================
resource "google_compute_region_network_endpoint_group" "serverless_neg" {
  name                  = "${local.name_prefix}dc-serverless-neg"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = var.cloud_run_service_name
  }
}

# =============================================================================
# 3. Global Backend Service
# =============================================================================
resource "google_compute_backend_service" "backend" {
  name                  = "${local.name_prefix}dc-backend-service"
  project               = var.project_id
  protocol              = "HTTP"
  enable_cdn            = false
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.serverless_neg.id
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

# =============================================================================
# 4. URL Map & Target HTTP Proxy
# =============================================================================
resource "google_compute_url_map" "url_map" {
  name            = "${local.name_prefix}dc-url-map"
  project         = var.project_id
  default_service = google_compute_backend_service.backend.id
}

resource "google_compute_target_http_proxy" "http_proxy" {
  name    = "${local.name_prefix}dc-http-proxy"
  project = var.project_id
  url_map = google_compute_url_map.url_map.id
}

# =============================================================================
# 5. Global Forwarding Rule (Port 80)
# =============================================================================
resource "google_compute_global_forwarding_rule" "forwarding_rule" {
  name                  = "${local.name_prefix}dc-forwarding-rule"
  project               = var.project_id
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.http_proxy.id
  ip_address            = google_compute_global_address.lb_ip.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
