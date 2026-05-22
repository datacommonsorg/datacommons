variable "project_id" {
  type = string
}

variable "namespace" {
  type = string
}

variable "dc_api_key" {
  type = string
}

variable "maps_api_key" {
  type    = string
  default = null
}

variable "create_maps_key" {
  type    = bool
  default = true
}

