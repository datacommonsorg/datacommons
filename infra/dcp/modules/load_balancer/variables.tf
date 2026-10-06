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
}

variable "enable_cloud_armor" {
  description = "Enable Cloud Armor security policy with IP rate limiting and WAF rules on the load balancer backend."
  type        = bool
  default     = true
}

variable "rate_limit_requests_per_minute" {
  description = "Maximum requests per minute allowed per client IP before rate limiting (HTTP 429) is enforced."
  type        = number
  default     = 120
}

variable "rate_limit_ban_duration_sec" {
  description = "Duration in seconds to ban a client IP that exceeds the rate limit threshold."
  type        = number
  default     = 600
}

variable "enable_owasp_waf_rules" {
  description = "Enable preconfigured OWASP Top 10 WAF protection rules (SQLi, XSS, LFI, RFI) in Cloud Armor."
  type        = bool
  default     = true
}

variable "allowed_ip_ranges" {
  description = "List of CIDR IP ranges allowed to access the Load Balancer. Defaults to ['*'] (all public IPs)."
  type        = list(string)
  default     = ["*"]
}

