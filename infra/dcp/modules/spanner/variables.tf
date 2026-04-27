variable "namespace" {
  type = string
}

variable "region" {
  type = string
}

variable "create_spanner_instance" {
  type = bool
}

variable "create_spanner_db" {
  type = bool
}

variable "spanner_instance_id" {
  type = string
}

variable "spanner_database_id" {
  type = string
}

variable "spanner_processing_units" {
  type = number
}

variable "deletion_protection" {
  type = bool
}
