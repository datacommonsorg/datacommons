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

variable "network_id" {
  type        = string
  description = "VPC network ID or self_link for Direct VPC Egress"
  default     = null
}

variable "subnet_id" {
  type        = string
  description = "Subnet ID or self_link for Direct VPC Egress"
  default     = null
}

variable "vpc_egress_mode" {
  type        = string
  description = "VPC egress mode (PRIVATE_RANGES_ONLY or ALL_TRAFFIC)"
  default     = "PRIVATE_RANGES_ONLY"
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

variable "skip_container_restarts" {
  type        = bool
  description = "Set to true to skip updating container restart timestamps, speeding up terraform apply when container images have not changed."
  default     = false
}
