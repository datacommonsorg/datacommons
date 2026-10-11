terraform {
  required_version = ">= 1.5.0"
}

variable "status" {
  type    = string
  default = "active"
}

locals {
  message = "hello-${var.status}"
}
