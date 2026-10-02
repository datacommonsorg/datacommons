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

variable "spanner_config" {
  type = object({
    instance_id = string
    database_id = string
  })
  description = "Spanner database coordinates for dataflow graph loading"
}
