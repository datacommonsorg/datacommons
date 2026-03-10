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

variable "create_spanner" {
  description = "Whether to create a new Spanner instance and database"
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

variable "cpu" {
  description = "Number of CPUs"
  type        = string
}

variable "memory" {
  description = "Amount of Memory"
  type        = string
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
}

variable "concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
}

variable "timeout_seconds" {
  description = "Request timeout in seconds"
  type        = number
}

variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
}
