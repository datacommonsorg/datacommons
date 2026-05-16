variable "namespace" {
  type = string
}

variable "region" {
  type = string
}

variable "redis_instance_name" {
  type = string
}

variable "redis_memory_size_gb" {
  type = number
}

variable "redis_tier" {
  type = string
}

variable "redis_location_id" {
  type = string
}

variable "redis_alternative_location_id" {
  type = string
}

variable "redis_replica_count" {
  type = number
}

variable "vpc_network_id" {
  type = string
}
