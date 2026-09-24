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
  type        = string
  description = "The VPC network ID or self_link to peer the Redis instance to"
}

variable "enable_auth" {
  type        = bool
  description = "Enable Redis AUTH (password authentication) on the Memorystore instance"
  default     = true
}

variable "enable_tls" {
  type        = bool
  description = "Enable in-transit TLS encryption (SERVER_AUTHENTICATION) on the Memorystore instance"
  default     = true
}
