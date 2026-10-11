# Continuous Integration Prober — Terraform Blueprint (`deploy/terraform`)

This directory contains the Terraform blueprint that provisions the automated 24/7 DCP Integration Prober on Google Cloud.

## Directory Structure

```
tests/integration/prober/deploy/terraform/
├── main.tf              # Cloud Run Job, Scheduler cron, GCS bucket, and Monitoring alert resources
├── variables.tf         # Project ID, prober name, schedule, alert email, and location inputs
├── outputs.tf           # Exported service account, bucket names, and job IDs
├── backend.tf           # Dynamic GCS remote state configuration (populated during deploy)
└── .terraform.lock.hcl  # HashiCorp Google provider dependency lockfile
```

## Validation & Formatting Commands

The repository CI workflow (`.github/workflows/ci.yaml`) validates this configuration on pull requests. Run these commands locally before submitting changes:

### 1. Check Formatting
```bash
terraform fmt -check -diff -recursive tests/integration/prober/deploy/terraform
```

### 2. Format In-Place
```bash
terraform fmt -recursive tests/integration/prober/deploy/terraform
```

### 3. Initialize & Validate Syntax
```bash
# Initialize provider plugins without remote state backend
terraform -chdir=tests/integration/prober/deploy/terraform init -backend=false

# Validate internal configuration consistency
terraform -chdir=tests/integration/prober/deploy/terraform validate
```

> **Deployment Runbook**: To deploy or update the prober infrastructure on GCP, refer to the parent [Prober Deployment Runbook](../README.md).
