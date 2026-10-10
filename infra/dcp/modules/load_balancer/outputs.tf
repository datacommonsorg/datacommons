output "load_balancer_ip" {
  description = "The global external Anycast IP address assigned to the Load Balancer."
  value       = google_compute_global_address.lb_ip.address
}

output "load_balancer_url" {
  description = "The HTTP entrypoint URL for the Load Balancer."
  value       = "http://${google_compute_global_address.lb_ip.address}"
}

output "backend_service_id" {
  description = "ID of the global compute backend service."
  value       = google_compute_backend_service.backend.id
}

output "cloud_armor_policy_id" {
  description = "ID of the Cloud Armor security policy attached to the Load Balancer backend, if enabled."
  value       = try(one(google_compute_security_policy.cloud_armor[*].id), null)
}

