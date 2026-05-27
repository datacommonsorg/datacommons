variable "deploy" {
  type = bool
}

variable "project_id" {
  type = string
}

variable "namespace" {
  type = string
}

variable "ingestion_bucket_name" {
  type = string
}

variable "use_spanner" {
  type    = bool
  default = true
}

variable "foundation_dependency" {
  description = "An artificial dependency to delay resource creation until APIs are ready."
  type        = any
  default     = null
}

