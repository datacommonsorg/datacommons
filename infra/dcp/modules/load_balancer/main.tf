locals {
  name_prefix            = var.instance_name != "" ? "${var.instance_name}-" : ""
  restrict_ip_allowlist  = length(var.allowed_ip_ranges) > 0 && !contains(var.allowed_ip_ranges, "*")
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
# 3. Cloud Armor Security Policy (Rate Limiting, IP Allowlisting & OWASP WAF)
# =============================================================================
resource "google_compute_security_policy" "cloud_armor" {
  count       = var.enable_cloud_armor ? 1 : 0
  name        = "${local.name_prefix}dc-cloud-armor-policy"
  project     = var.project_id
  description = "Cloud Armor edge security policy for Data Commons Serving Load Balancer"

  # Rules 1001-1003: Preconfigured OWASP Top 10 WAF Rules (XSS, LFI, RFI)
  # Note: sqli-v33-stable is omitted because its id942200 rule flags '->' and '<-' which are core Data Commons graph syntax.
  dynamic "rule" {
    for_each = var.enable_owasp_waf_rules ? {
      1001 = { expr = "evaluatePreconfiguredWaf('xss-v33-stable')", desc = "OWASP Cross-Site Scripting (XSS) protection" }
      1002 = { expr = "evaluatePreconfiguredWaf('lfi-v33-stable')", desc = "OWASP Local File Inclusion (LFI) protection" }
      1003 = { expr = "evaluatePreconfiguredWaf('rfi-v33-stable')", desc = "OWASP Remote File Inclusion (RFI) protection" }
    } : {}
    content {
      action      = "deny(403)"
      priority    = tonumber(rule.key)
      description = rule.value.desc
      match {
        expr {
          expression = rule.value.expr
        }
      }
    }
  }

  # Rule 2000: Adaptive Per-IP Rate Limiting (HTTP 429)
  rule {
    action      = "rate_based_ban"
    priority    = 2000
    description = "Rate-based throttling per client IP (${var.rate_limit_requests_per_minute} req/min)"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = var.allowed_ip_ranges
      }
    }
    rate_limit_options {
      conform_action   = "allow"
      exceed_action    = "deny(429)"
      enforce_on_key   = "IP"
      ban_duration_sec = var.rate_limit_ban_duration_sec

      rate_limit_threshold {
        count        = var.rate_limit_requests_per_minute
        interval_sec = 60
      }
    }
  }

  # Default Rule (Priority 2147483647): Deny(403) when IP allowlist is active, otherwise Allow
  rule {
    action      = local.restrict_ip_allowlist ? "deny(403)" : "allow"
    priority    = 2147483647
    description = local.restrict_ip_allowlist ? "Default rule: block unallowed IPs" : "Default rule: allow legitimate traffic"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}

# =============================================================================
# 4. Global Backend Service
# =============================================================================
resource "google_compute_backend_service" "backend" {
  name                  = "${local.name_prefix}dc-backend-service"
  project               = var.project_id
  protocol              = "HTTP"
  enable_cdn            = false
  load_balancing_scheme = "EXTERNAL_MANAGED"
  security_policy       = var.enable_cloud_armor ? google_compute_security_policy.cloud_armor[0].id : null

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
