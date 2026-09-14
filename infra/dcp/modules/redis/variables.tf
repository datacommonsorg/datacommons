variable "instance_name" {
  type = string
}

variable "region" {
  type = string
}

variable "redis_instance_name" {
  type    = string
  default = ""
}

variable "memory_size_gb" {
  type = number
}

variable "tier" {
  type = string
}

variable "location_id" {
  type = string
}

variable "alternative_location_id" {
  type = string
}

variable "replica_count" {
  type = number
}

variable "vpc_network_id" {
  type = string
}

variable "vpc_connector_cidr" {
  type    = string
  default = ""
}

variable "enable_connector" {
  type    = bool
  default = true
}

variable "vpc_connector_min_instances" {
  type        = number
  description = "Minimum number of VPC Access Connector instances."
  default     = 2
}

variable "vpc_connector_max_instances" {
  type        = number
  description = "Maximum number of VPC Access Connector instances."
  default     = 10
}
