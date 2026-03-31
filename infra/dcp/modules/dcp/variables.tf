variable "namespace" {
  description = "Global prefix for resources"
  type        = string
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "image_url" {
  description = "Docker image URL to deploy"
  type        = string
}

variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string
}

variable "service_account_name" {
  description = "Name of the Service Account to create/use"
  type        = string
}

variable "create_spanner_instance" {
  description = "Whether to create a new Spanner instance"
  type        = bool
}

variable "create_spanner_db" {
  description = "Whether to create a new Spanner database"
  type        = bool
}

variable "spanner_instance_id" {
  description = "Spanner Instance ID"
  type        = string
}

variable "spanner_database_id" {
  description = "Spanner Database ID"
  type        = string
}

variable "spanner_processing_units" {
  description = "Spanner Processing Units"
  type        = number
}

variable "service_cpu" {
  description = "CPU limit for the service container"
  type        = string
}

variable "service_memory" {
  description = "Memory limit for the service container"
  type        = string
}

variable "service_min_instances" {
  description = "Minimum number of service instances"
  type        = number
}

variable "service_max_instances" {
  description = "Maximum number of service instances"
  type        = number
}

variable "service_concurrency" {
  description = "Maximum concurrent requests per service instance"
  type        = number
}

variable "service_timeout_seconds" {
  description = "Request timeout in seconds for the service"
  type        = number
}

variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
}

variable "make_service_public" {
  description = "Whether to allow unauthenticated invocations to the service"
  type        = bool
}
