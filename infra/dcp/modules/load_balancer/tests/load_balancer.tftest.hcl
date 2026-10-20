# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Unit tests for the load_balancer module (plan-only, mocked provider).
mock_provider "google" {}

variables {
  project_id             = "test-project"
  region                 = "us-central1"
  cloud_run_service_name = "test-service"
}

# -----------------------------------------------------------------------------
# Cloud Armor defaults & validation
# -----------------------------------------------------------------------------
run "defaults_enable_cloud_armor_with_waf" {
  command = plan

  assert {
    condition     = length(google_compute_security_policy.cloud_armor) == 1
    error_message = "Cloud Armor policy should be created by default"
  }

  assert {
    condition     = length([for r in google_compute_security_policy.cloud_armor[0].rule : r if r.priority == 1001 || r.priority == 1002]) == 2
    error_message = "XSS (1001) and LFI (1002) WAF rules should be enabled by default"
  }
}

run "cidr_allowlist_accepted" {
  command = plan

  variables {
    allowed_ip_ranges = ["203.0.113.4/32", "10.0.0.0/8"]
  }
}

run "invalid_cidr_rejected" {
  command = plan

  variables {
    allowed_ip_ranges = ["<YOUR_IP>/32"]
  }

  expect_failures = [var.allowed_ip_ranges]
}

run "wildcard_mixed_with_cidrs_rejected" {
  command = plan

  variables {
    allowed_ip_ranges = ["*", "10.0.0.0/8"]
  }

  expect_failures = [var.allowed_ip_ranges]
}

run "more_than_ten_cidrs_rejected" {
  command = plan

  variables {
    allowed_ip_ranges = [
      "1.1.1.1/32", "1.1.1.2/32", "1.1.1.3/32", "1.1.1.4/32", "1.1.1.5/32", "1.1.1.6/32",
      "1.1.1.7/32", "1.1.1.8/32", "1.1.1.9/32", "1.1.1.10/32", "1.1.1.11/32",
    ]
  }

  expect_failures = [var.allowed_ip_ranges]
}

run "ban_duration_below_minimum_rejected" {
  command = plan

  variables {
    rate_limit_ban_duration_sec = 30
  }

  expect_failures = [var.rate_limit_ban_duration_sec]
}

# -----------------------------------------------------------------------------
# HTTPS
# -----------------------------------------------------------------------------
run "no_domains_is_http_only" {
  command = plan

  assert {
    condition = (
      length(google_compute_managed_ssl_certificate.cert) == 0 &&
      length(google_compute_target_https_proxy.https_proxy) == 0 &&
      length(google_compute_global_forwarding_rule.https_forwarding_rule) == 0 &&
      length(google_compute_url_map.https_redirect) == 0
    )
    error_message = "No HTTPS resources should be created without domains"
  }

  assert {
    condition     = startswith(output.load_balancer_url, "http://")
    error_message = "load_balancer_url should be http://<ip> without domains"
  }
}

run "domains_enable_https_with_redirect" {
  command = plan

  variables {
    domains = ["data.example.org"]
  }

  assert {
    condition = (
      length(google_compute_managed_ssl_certificate.cert) == 1 &&
      length(google_compute_target_https_proxy.https_proxy) == 1 &&
      length(google_compute_global_forwarding_rule.https_forwarding_rule) == 1 &&
      length(google_compute_url_map.https_redirect) == 1
    )
    error_message = "Domains should create cert, HTTPS proxy, 443 forwarding rule and HTTP redirect"
  }

  assert {
    condition     = google_compute_global_forwarding_rule.https_forwarding_rule[0].port_range == "443"
    error_message = "HTTPS forwarding rule must listen on 443"
  }

  assert {
    condition     = output.load_balancer_url == "https://data.example.org"
    error_message = "load_balancer_url should be https://<first domain>"
  }
}

run "domains_without_redirect" {
  command = plan

  variables {
    domains        = ["data.example.org"]
    https_redirect = false
  }

  assert {
    condition     = length(google_compute_url_map.https_redirect) == 0 && length(google_compute_target_https_proxy.https_proxy) == 1
    error_message = "HTTPS should be enabled without the HTTP redirect"
  }
}

run "ip_address_domain_rejected" {
  command = plan

  variables {
    domains = ["34.102.209.210"]
  }

  expect_failures = [var.domains]
}

run "wildcard_domain_rejected" {
  command = plan

  variables {
    domains = ["*.example.org"]
  }

  expect_failures = [var.domains]
}
