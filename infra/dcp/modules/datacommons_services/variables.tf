# =============================================================================
# Global Configuration
# =============================================================================
variable "project_id" {
  type = string
}

variable "namespace" {
  type = string
}

variable "region" {
  type = string
}

variable "stateless_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for stateless resources (Cloud Run) to prevent accidental deletion."
}

# =============================================================================
# Container Configuration
# =============================================================================
variable "image" {
  type = string
}

variable "cpu" {
  type = string
}

variable "memory" {
  type = string
}

variable "min_instances" {
  type = number
}

variable "max_instances" {
  type = number
}

# =============================================================================
# Feature Toggles & Configuration
# =============================================================================
variable "make_public" {
  type = bool
}

variable "google_analytics_tag_id" {
  type    = string
  default = null
}

variable "enable_mcp" {
  type = bool
}

variable "mcp_search_scope" {
  type = string
}

variable "mcp_instructions_path" {
  type        = string
  description = "Path within the unified storage bucket for customized instructions for server tools and agents"
  default     = null
}

# =============================================================================
# Infrastructure References
# =============================================================================
variable "artifacts_bucket_name" {
  type        = string
  description = "Name of the unified GCS bucket for artifacts"
  default     = ""
}

variable "vpc_connector_id" {
  type = string
}

variable "use_spanner" {
  type = bool
}

# =============================================================================
# Shared Environment Variables
# =============================================================================
variable "env_vars" {
  type = list(object({
    name  = string
    value = string
  }))
}

variable "secret_env_vars" {
  type = list(object({
    name    = string
    secret  = string
    version = string
  }))
}

variable "foundation_dependency" {
  description = "An artificial dependency to delay resource creation until APIs are ready."
  type        = any
  default     = null
}


