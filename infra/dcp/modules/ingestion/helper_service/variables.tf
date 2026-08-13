variable "deploy" {
  type = bool
}

variable "project_id" {
  type = string
}

variable "instance_name" {
  type = string
}

variable "region" {
  type = string
}

variable "stateless_deletion_protection" {
  type        = bool
  description = "Enable deletion protection for stateless resources (Cloud Run) to prevent accidental deletion."
}

variable "spanner_instance_id" {
  type = string
}

variable "spanner_database_id" {
  type = string
}

variable "ingestion_bucket_name" {
  type = string
}

variable "image" {
  type        = string
  nullable    = false
  description = "Docker image URL for the ingestion support service"
}

variable "use_spanner" {
  type    = bool
  default = true
}


variable "enable_embeddings_generation" {
  type        = bool
  description = "Flag to enable embedding generation"
}

variable "vpc_connector_id" {
  type        = string
  description = "VPC access connector ID for Cloud Run"
  default     = ""
}

variable "redis_host" {
  type        = string
  description = "Redis host IP"
  default     = ""
}

variable "redis_port" {
  type        = string
  description = "Redis port"
  default     = "6379"
}

variable "ingestion_artifacts_path" {
  type        = string
  description = "Path where pre-processed files are placed for the next stage"
}

variable "cpu_idle" {
  type        = bool
  description = "When true, CPU is only allocated during request processing (cheaper for low-traffic services). When false, CPU is always allocated."
  default     = false
}

variable "startup_cpu_boost" {
  type        = bool
  description = "Temporarily boost CPU allocation during container startup to reduce cold start latency."
  default     = true
}

variable "skip_container_restarts" {
  type        = bool
  description = "Set to true to skip updating container restart timestamps, speeding up terraform apply when container images have not changed."
  default     = false
}
