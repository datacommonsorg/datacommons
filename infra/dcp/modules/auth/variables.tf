variable "project_id" {
  type = string
}

variable "instance_name" {
  type = string
}

variable "dc_api_key_secret_id" {
  description = "Name of the Secret Manager secret in project_id that holds the Data Commons API key. Defaults to \"<instance_name>-dc-api-key\" (created by `datacommons-admin init`)."
  type        = string
  default     = ""

  validation {
    condition     = var.dc_api_key_secret_id == "" || can(regex("^[A-Za-z0-9_-]+$", var.dc_api_key_secret_id))
    error_message = "dc_api_key_secret_id must be a secret name in project_id (e.g. \"my-dc-api-key\"), not a full resource path."
  }
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





