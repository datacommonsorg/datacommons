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
