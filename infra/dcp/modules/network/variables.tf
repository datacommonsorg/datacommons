# =============================================================================
# Global Configuration
# =============================================================================
variable "project_id" {
  type        = string
  description = "GCP Project ID"
}

variable "region" {
  type        = string
  description = "GCP Region for regional resources (subnets, routers)"
}

variable "instance_name" {
  type        = string
  description = "Instance name prefix for resource naming"
  default     = ""
}

# =============================================================================
# Network Toggles & Configuration
# =============================================================================
variable "enable" {
  type        = bool
  description = "Whether VPC networking infrastructure is enabled for DCP"
  default     = true
}

variable "enable_workload_vpc" {
  type        = bool
  description = "Whether compute workloads (Cloud Run, Dataflow) attach to the VPC. Set to false to cleanly detach workloads before destroying the network."
  default     = true
}

variable "vpc_egress_mode" {
  type        = string
  description = "VPC egress mode for Cloud Run services and jobs (PRIVATE_RANGES_ONLY or ALL_TRAFFIC)"
  default     = "PRIVATE_RANGES_ONLY"
}

variable "create_vpc" {
  type        = bool
  description = "Whether to provision a new custom VPC network and subnet. Set to false when attaching to an existing or Shared VPC."
  default     = true
}

variable "network_name" {
  type        = string
  description = "Name of the custom VPC network to create, or name of existing network"
  default     = "dc-vpc"
}

variable "subnet_cidr" {
  type        = string
  description = "CIDR range for the private subnetwork (e.g., 10.0.0.0/24)"
  default     = "10.0.0.0/24"
}

variable "enable_cloud_nat" {
  type        = bool
  description = "Whether to provision Cloud Router and Cloud NAT for outbound internet egress from private workers"
  default     = false
}

# =============================================================================
# Existing / Shared VPC Integration
# =============================================================================
variable "existing_network_id" {
  type        = string
  description = "Network self_link or ID when attaching to an existing/Shared VPC (when create_vpc = false)"
  default     = null
}

variable "existing_subnet_id" {
  type        = string
  description = "Subnet self_link or ID when attaching to an existing/Shared VPC (when create_vpc = false)"
  default     = null
}
