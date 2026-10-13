output "load_balancer_ip" {
  description = "The global external Anycast IP address assigned to the Load Balancer."
  value       = google_compute_global_address.lb_ip.address
}

output "load_balancer_url" {
  description = "The HTTP entrypoint URL for the Load Balancer."
  value       = "http://${google_compute_global_address.lb_ip.address}"
}

output "backend_service_id" {
  description = "ID of the global compute backend service (useful for attaching Cloud Armor security policies in Phase 2)."
  value       = google_compute_backend_service.backend.id
}
