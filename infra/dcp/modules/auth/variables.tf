variable "project_id" {
  type = string
}

variable "namespace" {
  type = string
}

variable "dc_api_key" {
  type = string
}

variable "google_maps_api_key" {
  type    = string
  default = null
}


variable "create_google_maps_key" {
  type    = bool
  default = true
}




