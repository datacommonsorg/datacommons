variable "namespace" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_network_name" {
  type = string
}

variable "vpc_connector_cidr" {
  type = string
}

variable "enable_connector" {
  type    = bool
  default = false
}

