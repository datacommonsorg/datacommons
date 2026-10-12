variable "project_id" { type = string }
variable "instance_name" { type = string }

variable "env_secrets" {
  type = map(object({
    secret_id = string
    enabled   = bool
    version   = optional(string, "latest")
  }))
  default     = {}
  description = <<-EOT
    Map of secrets to grant access to and mount in the job, where the key is the environment variable name.
    Example:
    {
      "DC_API_KEY" = {
        secret_id = "projects/my-project/secrets/my-secret"
        enabled   = true
        version   = "latest" # Optional, defaults to "latest"
      }
    }
  EOT
}