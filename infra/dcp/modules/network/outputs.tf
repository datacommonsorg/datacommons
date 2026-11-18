output "network_id" {
  description = "The ID of the VPC network"
  value       = local.effective_network_id
}

output "network_name" {
  description = "The name of the VPC network"
  value       = local.effective_network_name
}

output "subnet_id" {
  description = "The ID of the private subnetwork (for Direct VPC Egress)"
  value       = local.effective_subnet_id
}

output "subnet_url" {
  description = "The self_link / URL of the subnetwork (for Dataflow workers)"
  value       = local.effective_subnet_url
}

output "vpc_access" {
  description = "Unified Direct VPC Egress configuration object for Cloud Run, or null if disabled"
  value = var.enable && var.enable_workload_vpc ? {
    network_id      = local.effective_network_id
    subnet_id       = local.effective_subnet_id
    vpc_egress_mode = var.vpc_egress_mode
  } : null
}
