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
