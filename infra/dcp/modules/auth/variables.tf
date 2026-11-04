variable "project_id" {
  type = string
}

variable "instance_name" {
  type = string
}

variable "dc_api_key_secret_id" {
  description = "Secret Manager secret ID or full resource name (projects/<project>/secrets/<secret>) containing the Data Commons API key. When provided, Terraform skips creating a managed secret."
  type        = string
  default     = ""
}

variable "dc_api_key" {
  description = "Deprecated: Plaintext Data Commons API key. Prefer dc_api_key_secret_id so the secret value is not stored in Terraform state."
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_maps_api_key" {
  type      = string
  default   = null
  sensitive = true
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





