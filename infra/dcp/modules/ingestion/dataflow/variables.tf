variable "deploy" {
  type = bool
}

variable "project_id" {
  type = string
}

variable "instance_name" {
  type = string
}

variable "ingestion_bucket_name" {
  type = string
}

variable "use_spanner" {
  type    = bool
  default = true
}

