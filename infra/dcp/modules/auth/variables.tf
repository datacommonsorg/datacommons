variable "project_id" {
  type = string
}

variable "instance_name" {
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

variable "google_maps_allowed_referrers" {
  description = "A list of HTTP referrers allowed to use the Google Maps API key (e.g. ['https://example.com/*', 'http://localhost:*']). If empty, no browser referrer restrictions are enforced."
  type        = list(string)
  default     = []
}




