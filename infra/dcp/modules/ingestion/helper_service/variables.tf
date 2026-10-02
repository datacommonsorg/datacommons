
variable "project_id" {
  type        = string
  description = "The GCP project ID where resources will be deployed"
}

variable "instance_name" {
  type        = string
  description = "Instance identifier used for resource naming prefix"
}

variable "region" {
  type        = string
  description = "The GCP region for the Cloud Run service"
}

variable "stateless_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for stateless resources (Cloud Run) to prevent accidental deletion."
}

variable "spanner_config" {
  type = object({
    instance_id = string
    database_id = string
  })
  description = "Spanner database coordinates"
}

variable "ingestion_bucket_name" {
  type        = string
  description = "Name of the GCS bucket used for ingestion artifacts and records"
}

variable "image" {
  type        = string
  nullable    = false
  description = "Docker image URL for the ingestion support service"
}

variable "enable_embeddings_generation" {
  type        = bool
  description = "Flag to enable embedding generation"
}

variable "vpc_access" {
  type = object({
    network_id      = string
    subnet_id       = string
    vpc_egress_mode = optional(string, "PRIVATE_RANGES_ONLY")
  })
  description = "Direct VPC Egress configuration. If null, service runs without VPC egress."
  default     = null
}

variable "redis_config" {
  type = object({
    host           = string
    port           = optional(string, "6379")
    auth_secret_id = optional(string, null)
    ca_cert        = optional(string, "")
  })
  description = "Optional Redis cache configuration for cache coordination and invalidation"
  default     = null
}

variable "ingestion_artifacts_path" {
  type        = string
  description = "Path where pre-processed files are placed for the next stage"
}

variable "skip_container_restarts" {
  type        = bool
  description = "Set to true to skip updating container restart timestamps, speeding up terraform apply when container images have not changed."
  default     = false
}
