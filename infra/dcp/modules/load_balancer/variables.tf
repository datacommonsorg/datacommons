variable "project_id" {
  description = "The GCP project ID where the load balancer will be created."
  type        = string
}

variable "region" {
  description = "The GCP region where the Cloud Run backend service is located."
  type        = string
}

variable "instance_name" {
  description = "Instance name prefix for resource naming and isolation."
  type        = string
  default     = ""
}

variable "cloud_run_service_name" {
  description = "Name of the Cloud Run service to attach as a backend."
  type        = string
  default     = null
}

variable "enable_cloud_armor" {
  description = "Enable Cloud Armor security policy with IP rate limiting and WAF rules on the load balancer backend."
  type        = bool
  default     = true
}

variable "rate_limit_requests_per_minute" {
  description = "Maximum requests per minute allowed per client IP before rate limiting (HTTP 429) is enforced."
  type        = number
  default     = 600
}

variable "rate_limit_ban_duration_sec" {
  description = "Duration in seconds a client IP that exceeded the rate limit stays banned (HTTP 429) after its request rate falls back below the threshold."
  type        = number
  default     = 60

  validation {
    condition     = var.rate_limit_ban_duration_sec >= 60 && var.rate_limit_ban_duration_sec <= 3600
    error_message = "The rate_limit_ban_duration_sec must be between 60 and 3600 seconds."
  }
}

variable "enable_owasp_waf_rules" {
  description = "Enable preconfigured OWASP Top 10 WAF protection rules (XSS, LFI) in Cloud Armor."
  type        = bool
  default     = true
}

variable "allowed_ip_ranges" {
  description = "List of CIDR IP ranges allowed to access the Load Balancer. Defaults to ['*'] (all public IPs)."
  type        = list(string)
  default     = ["*"]

  validation {
    condition     = length(var.allowed_ip_ranges) > 0 && length(var.allowed_ip_ranges) <= 10
    error_message = "The allowed_ip_ranges list must contain between 1 and 10 CIDR ranges (or ['*'])."
  }

  validation {
    condition     = alltrue([for r in var.allowed_ip_ranges : r == "*" || can(cidrhost(r, 0))])
    error_message = "Each entry in allowed_ip_ranges must be a valid CIDR range (e.g. '203.0.113.4/32') or '*'."
  }

  validation {
    condition     = !contains(var.allowed_ip_ranges, "*") || length(var.allowed_ip_ranges) == 1
    error_message = "When '*' is used in allowed_ip_ranges it must be the only entry."
  }
}


variable "domains" {
  description = "Domains for the Google-managed SSL certificate. When non-empty, an HTTPS listener (port 443) is created. DNS A records for each domain must point at the load balancer IP for the certificate to provision."
  type        = list(string)
  default     = []

  validation {
    condition     = length(var.domains) <= 100 && alltrue([for d in var.domains : can(regex("^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,63}$", d))])
    error_message = "domains must be at most 100 lowercase fully-qualified hostnames (e.g. 'data.example.org'); wildcards and IPs are not supported."
  }
}

variable "https_redirect" {
  description = "When HTTPS is enabled, redirect all HTTP (port 80) requests to HTTPS at the load balancer. Defaults to false so HTTP keeps working while the managed certificate provisions; enable once the certificate is ACTIVE."
  type        = bool
  default     = false
}
