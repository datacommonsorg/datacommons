# Data Commons Platform Infrastructure Guide (`infra/dcp`)

This directory contains the root Terraform configurations for deploying the Data Commons Platform (DCP) on Google Cloud Platform (GCP).

* **New to DCP?** Walk through the hands-on [Developer Onboarding Codelab](../../docs/codelabs/dcp_developer_onboarding.md) to set up and deploy a test instance step by step.
* **Architecture Deep Dive**: Consult [Terraform Stack Architecture](../../docs/architecture/terraform_stack.md) for the dual entrypoint design, cross-module IAM wiring, and variable propagation pipelines.

---

## Module Hierarchy

Infrastructure composition is orchestrated by `modules/stack/main.tf`, which connects the following modular components (see [Terraform Stack Architecture](../../docs/architecture/terraform_stack.md#stack-orchestration-and-module-topology) for a detailed breakdown of module responsibilities):

```
infra/dcp/
├── main.tf                  # Root entrypoint aggregating variables into typed config objects
├── variables.tf             # Schema declarations for all root inputs
├── outputs.tf               # Exported deployment attributes
├── terraform.tfvars.template# Template populated by the CLI or local operator
├── scripts/                 # Test scripts
│   └── check_terraform.py   # Pre-commit runner (fmt, validate, unit tests)
│
└── modules/
    ├── stack/               # Central wiring hub (IAM, shared env vars, cross-module links)
    ├── auth/                # Secret Manager keys for Data Commons and Maps APIs
    ├── spanner/             # Cloud Spanner instance, databases, and BigQuery connections
    ├── storage/             # GCS artifacts bucket
    ├── redis/               # MemoryStore Redis and VPC Access connector
    ├── datacommons_services/# Cloud Run serving container (Envoy + Mixer + Website)
    │
    ├── ingestion/           # Ingestion pipeline submodules
    │   ├── preprocessing_job# Service account and IAM for Cloud Batch preprocessing (datacommons-data)
    │   ├── dataflow/        # Service accounts and IAM for Apache Beam Java Dataflow
    │   ├── postprocessing_job # Cloud Run job executing aggregation queries
    │   ├── helper_service/  # FastAPI Cloud Run service managing locks and embeddings
    │   └── workflow/        # Google Cloud Workflows orchestration definition
    │
    └── */tests/*.tftest.hcl # Hermetic unit tests per module (e.g. datacommons_services/tests/)
```

> [!IMPORTANT]
> Keep `source = "./modules/stack"` on a single line in [main.tf](main.tf); `datacommons admin init` matches this exact string when rewriting the module source to a remote GitHub release tag.

---

## Quickstart Commands

Run standard Terraform operations directly within this directory when testing or contributing to infrastructure modules.

```bash
# 1. Prepare local configuration
cp terraform.tfvars.template terraform.tfvars

# 2. Authenticate to Google Cloud
gcloud auth login
gcloud auth application-default login
gcloud config set project <your-project-id>

# 3. Initialize provider plugins and modules
terraform init

# 4. Review proposed changes
terraform plan

# 5. Apply infrastructure mutations
terraform apply

# 6. View exported deployment outputs
terraform output
```

> **Local Testing Recipes**: To test local module changes from a scaffolded workspace using local paths or symlinks, or to test against specific released DCP versions vs head, refer to the [Developer Guide](../../docs/developer_guide.md#testing-local-module-changes-in-a-scaffolded-workspace).

---

## Configuration Reference

The authoritative source of truth for all configuration options, type constraints, descriptions, and active default values is [variables.tf](variables.tf). To inspect a starter configuration template, consult [terraform.tfvars.template](terraform.tfvars.template).

### Key Variable Groups

* **Instance Identity and Authentication**:
  * `project_id`: Target Google Cloud Project ID.
  * `instance_name`: Unique namespace prefix for provisioned GCP resources (such as `dev-alice`). Maximum 16 lowercase alphanumeric characters and hyphens.
  * `region`: Primary GCP compute and storage region.
  * `auth_google_datacommons_api_key`: Data Commons API Key from [apikeys.datacommons.org](https://apikeys.datacommons.org) for base knowledge graph federation.
* **Release and Image Management**:
  * `dcp_version`: Controls unified container image and template version resolution. Set to `"latest"` for bleeding-edge builds, or pin to a specific release tag (see [variables.tf](variables.tf) for current defaults and [Developer Guide](../../docs/developer_guide.md#running-the-stack-on-latest-main-and-latest-builds) for latest workflows).
  * `datacommons_services_image`, `ingestion_dataflow_template_gcs_path`: Individual container and template overrides when developing or testing custom builds.
* **Resource Safeguards**:
  * `stateful_deletion_protection`: Controls deletion protection on persistent storage layers (Cloud Spanner databases and GCS storage buckets; defaults are declared in [variables.tf](variables.tf)). Enable for production or persistent data protection.
  * `stateless_deletion_protection`: Controls deletion protection on Cloud Run services, jobs, and workflows (defaults are declared in [variables.tf](variables.tf)). Keep disabled for rapid development cycles.
* **Shared Project and Cost-Saving Overrides**:
  * `spanner_create_bigquery_reservation`: Set to `false` when sharing a GCP project or region, as GCP enforces a limit of one BigQuery reservation per project per region.
  * `spanner_create_instance`, `storage_create_artifacts_bucket`: Set to `false` when connecting to existing shared Spanner instances or pre-existing GCS buckets.
  * `enable_redis`: Provisions MemoryStore Redis and VPC Access connector for query caching (keep `false` for minimal test instances).

---

## Deployment Outputs

Run `terraform output` (or `terraform output -json`) after deployment to retrieve provisioned infrastructure attributes.

The authoritative source of truth for all exported attributes and descriptions is [outputs.tf](outputs.tf). The Admin CLI dynamically discovers and consumes these outputs during operational workflows (see [Admin CLI Architecture](../../docs/architecture/admin_cli.md#state-inspection-modes-local-vs-remote-gcs-state)).

---

## Local Development, Validation, and Testing

`scripts/check_terraform.py` checks formatting, validates the root configuration, and runs hermetic module unit tests (offline tests using mocked providers, requiring no GCP credentials). Requires **Terraform v1.7+**.

```bash
# Run all checks in read-only mode (fmt, validate, unit tests)
uv run infra/dcp/scripts/check_terraform.py

# Format all Terraform files in-place (cannot be combined with check flags)
uv run infra/dcp/scripts/check_terraform.py --fix

# Or run individual check phases (--fmt, --validate, --test can be combined)
uv run infra/dcp/scripts/check_terraform.py --fmt
uv run infra/dcp/scripts/check_terraform.py --validate
uv run infra/dcp/scripts/check_terraform.py --test
```

### Root Validation vs. Per-Module Unit Tests

* **Root Validation (`--validate`)**: Initializes and validates from the root (`infra/dcp`), checking the root module and all child modules wired into `modules/stack`. If you create a new module under `modules/` that is not yet connected to `modules/stack`, `terraform validate` will not check it.
* **Per-Module Unit Testing (`--test`)**: Discovers every `tests/` directory containing `*.tftest.hcl` files across `infra/dcp/modules/` and runs `terraform test` directly inside each module directory, even if the module is not yet wired into the root stack.

To run `terraform test` directly inside a single module during iteration:
```bash
terraform -chdir=infra/dcp/modules/datacommons_services init -backend=false
terraform -chdir=infra/dcp/modules/datacommons_services test
```

### Adding a Terraform Unit Test

Place unit tests for a module in `infra/dcp/modules/<module_name>/tests/<name>.tftest.hcl`. Use [`modules/datacommons_services/tests/service.tftest.hcl`](modules/datacommons_services/tests/service.tftest.hcl) as a reference template:
* Declare `mock_provider "google" {}` (requires Terraform `>= 1.7.0`) so Terraform simulates GCP API calls in memory without cloud credentials.
* Define shared required inputs in a top-level `variables {}` block, and override specific inputs inside each `run "<name>" { command = plan ... }` block.

#### What to Test
Unit tests automate the manual workflow of setting a variable one way, running `terraform plan`, flipping the variable the other way, and checking the planned output:
* **Assert on dynamic logic**: Test conditionals (`? :`), resource counts (`count`, `for_each`), `dynamic` blocks, `concat()` lists, and string interpolations.
* **Guard the baseline environment and IAM contract**: Use a single map assertion (`{ for e in ... : e.name => e.value if ... } == { ... }`) in `default_configuration` to verify required container environment variables, DCP constants (such as `IS_BASE_DC`), and baseline IAM roles in one check so they are never accidentally dropped during refactors.
* **Skip static infrastructure settings**: Do not write separate assertions for static resource settings (such as fixed port numbers or timeout values) that `terraform validate` already verifies.

#### Structuring Test Runs
Keep `.tftest.hcl` files fast and readable by grouping assertions into a minimal set of `run` blocks:
1. **`default_configuration`**: Supplies only required inputs (with optional toggles off or empty) and verifies default resource naming, baseline IAM bindings, the baseline container environment map, and the omission of optional resources or blocks.
2. **`custom_configuration`**: Enables independent optional features and overrides together in a single `plan` (for example, `instance_name` prefixing, public ingress, VPC egress, Secret Manager env vars, and custom paths) rather than adding separate single-assertion `run` blocks for each ternary.
3. **Targeted interaction runs (when warranted)**: Add 1–2 extra `run` blocks only when specific combinations of inputs interact in complex or mutually exclusive ways (for example, attaching to an existing Shared VPC vs. provisioning a new VPC, or testing `expect_failures` on input validation rules).

### Preventing Breaking State Changes (`moved` Blocks)

> [!WARNING]
> **Renaming or moving Terraform resources destroys and recreates live cloud resources unless you add a `moved` block.**
>
> Terraform tracks every deployed GCP resource in its state file by its exact code address (for example, `module.spanner[0].google_spanner_database.database`). If you rename a resource, move it between modules, or change whether a module/resource uses `count` or `for_each`, Terraform treats the old address as deleted and the new address as brand new—meaning the next `terraform apply` will **destroy the existing resource and recreate it**.
>
> To avoid accumulating state-migration clutter over time, apply this rule when refactoring resource addresses:
> * **Use `moved` blocks** for **stateful, user-facing, or foundational resources** where a teardown and recreate causes data loss, end-user downtime, or long provisioning delays (such as Cloud Spanner instances/databases, GCS buckets, VPC networking, Redis, or `datacommons-services`).
> * **Skip `moved` blocks** for **stateless internal resources** that can be torn down and recreated during `terraform apply` without data loss or user impact (such as ingestion Cloud Run jobs/helpers, Cloud Workflows, or monitoring alerts).
>
> When migrating a stateful or user-facing resource, declare a `moved` block in `modules/stack/` mapping `from` the old address `to` the new address:
> ```hcl
> moved {
>   from = module.spanner.google_spanner_database.database[0]
>   to   = module.spanner[0].google_spanner_database.database
> }
> ```
> This tells Terraform to update the state address in-place (`0 to destroy`) without touching the underlying GCP resource.

---

## Next Steps

* **Interactive Onboarding**: Follow [Developer Onboarding Codelab](../../docs/codelabs/dcp_developer_onboarding.md) to deploy, seed, ingest, and tear down an instance.
* **CLI Tooling**: Review [Admin CLI Architecture](../../docs/architecture/admin_cli.md) to understand how the CLI reads Terraform outputs and orchestrates jobs.
* **Database Migrations**: Refer to [Schema Migrations Developer Guide](../../docs/schema_migrations_developer_guide.md) for Spanner schema versioning procedures.
