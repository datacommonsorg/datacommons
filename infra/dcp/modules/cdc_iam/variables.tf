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

variable "disable_google_maps" {
  type    = bool
  default = false
}

variable "use_spanner" {
  type    = bool
  default = false
}
