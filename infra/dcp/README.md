# Data Commons Terraform Deployment (`infra/dcp`)

This directory contains Terraform for deploying both stacks:
- DCP (Data Commons Platform)
- CDC (Custom Data Commons)

The root configuration enables shared project APIs and delegates all stack composition to `modules/stack`.
The root module passes four grouped inputs into `modules/stack`: `shared`, `toggles`, `dcp`, and `cdc`.

## Module Layout

- `modules/stack` (single orchestration module called by root)

### CDC modules
- `modules/cdc_iam`
- `modules/cdc_mysql`
- `modules/cdc_redis`
- `modules/cdc_storage`
- `modules/cdc_network`
- `modules/cdc_data_ingestion_job`
- `modules/cdc_services`

### DCP modules
- `modules/spanner`
- `modules/dcp_service`
- `modules/dcp_storage`
- `modules/dcp_dataflow_ingestion`
- `modules/dcp_ingestion_workflow`

## High-Level Behavior

- Root keeps provider config and shared API enablement, then calls `module "stack"` for all CDC/DCP wiring.
- CDC can run with either:
  - MySQL (when `enable_cdc=true` and `enable_dcp=false`), or
  - Spanner from DCP (when both stacks are enabled).
- DCP ingestion flow splits orchestration and pipeline helper:
  - `dataflow_ingestion` manages ingestion helper + ingestion runner IAM.
  - `ingestion_workflow` manages Cloud Workflows orchestration.

## Key Inputs

- `enable_dcp`, `enable_cdc`
- `dcp_deploy_data_ingestion_workflow`
- `dcp_create_ingestion_bucket`
- `dcp_external_ingestion_bucket_name`
- `dcp_ingestion_lock_timeout`

## Deployment

1. Copy vars file:
```bash
cp terraform.tfvars.example terraform.tfvars
```

2. Initialize:
```bash
terraform init
```

3. Plan:
```bash
terraform plan
```

4. Apply:
```bash
terraform apply
```

## Validation Matrix

Run plans for:
- CDC only: `enable_cdc=true`, `enable_dcp=false`
- DCP only: `enable_cdc=false`, `enable_dcp=true`
- Both enabled: `enable_cdc=true`, `enable_dcp=true`

## Important Note

This modularization is recreate-acceptable and does not include state migration (`moved` blocks / state mv) in this pass.
