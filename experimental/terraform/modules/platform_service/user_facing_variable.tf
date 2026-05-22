# =============================================================================
# Serving Layer - Platform Service (Experimental)
# =============================================================================

variable "enable_platform_service" {
  description = "Enable the platform service for Data Commons"
  type        = bool
  default     = true
}

variable "platform_service_image" {
  description = "Docker image URL for the platform service component"
  type        = string
  default     = "gcr.io/datcom-ci/datacommons-platform:latest"
}

variable "platform_service_name" {
  description = "Cloud Run service name for the platform service component"
  type        = string
  default     = "dcp-svc"
}

variable "platform_service_account_name" {
  description = "Service account for the platform service component"
  type        = string
  default     = "dcp-sa"
}

variable "platform_service_cpu" {
  description = "CPU limit for the platform service container"
  type        = string
  default     = "1000m"
}

variable "platform_service_memory" {
  description = "Memory limit for the platform service container"
  type        = string
  default     = "1Gi"
}

variable "platform_service_min_instances" {
  description = "Minimum number of instances for the platform service"
  type        = number
  default     = 1
}

variable "platform_service_max_instances" {
  description = "Maximum number of instances for the platform service"
  type        = number
  default     = 10
}

variable "platform_service_concurrency" {
  description = "Maximum concurrent requests per instance for the platform service"
  type        = number
  default     = 80
}

variable "platform_service_timeout_seconds" {
  description = "Request timeout in seconds for the platform service"
  type        = number
  default     = 300
}
