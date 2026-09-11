# Data Commons Platform Infrastructure Guide (`infra/dcp`)

This directory contains the root Terraform configurations for deploying the Data Commons Platform (DCP) on Google Cloud Platform (GCP).

* **New to DCP?** Walk through the hands-on [Developer Onboarding Codelab](../../docs/codelabs/dcp_developer_onboarding.md) to set up and deploy a test instance step by step.
* **Architecture Deep Dive**: Consult [Terraform Stack Architecture](../../docs/architecture/terraform_stack.md) for module hierarchy, cross-module IAM wiring, and variable propagation pipelines.

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

> **Local Testing Recipes**: To test local module changes from a scaffolded workspace using local paths or symlinks, or to test against specific released DCP versions vs head, refer to the [Developer Guide](../../docs/developer_guide.md#working-on-infrastructure-infradcp).

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
  * `stateful_deletion_protection`: Controls deletion protection on persistent storage layers (Cloud Spanner databases and GCS storage buckets). Defaults to `false`; enable for production or persistent data protection.
  * `stateless_deletion_protection`: Controls deletion protection on Cloud Run services, jobs, and workflows. Keep `false` for rapid development cycles.
* **Shared Project and Cost-Saving Overrides**:
  * `spanner_create_bigquery_reservation`: Set to `false` when sharing a GCP project or region, as GCP enforces a limit of one BigQuery reservation per project per region.
  * `spanner_create_instance`, `storage_create_artifacts_bucket`: Set to `false` when connecting to existing shared Spanner instances or pre-existing GCS buckets.
  * `enable_redis`: Provisions MemoryStore Redis and VPC Access connector for query caching (keep `false` for minimal test instances).

---

## Deployment Outputs

Run `terraform output` (or `terraform output -json`) after deployment to retrieve provisioned infrastructure attributes.

The authoritative source of truth for all exported attributes and descriptions is [outputs.tf](outputs.tf). The Admin CLI dynamically discovers and consumes these outputs during operational workflows (see [Admin CLI Architecture](../../docs/architecture/admin_cli.md#state-inspection-modes-local-vs-remote-gcs-state)).

---

## Module Hierarchy

Infrastructure composition is orchestrated by `modules/stack/main.tf`, which connects the following modular components:

```
infra/dcp/
├── main.tf                  # Root entrypoint aggregating variables into typed config objects
├── variables.tf             # Schema declarations for all root inputs
├── outputs.tf               # Exported deployment attributes
├── terraform.tfvars.template# Template populated by the CLI or local operator
│
└── modules/
    ├── stack/               # Central wiring hub (IAM, shared env vars, cross-module links)
    ├── auth/                # Secret Manager keys for Data Commons and Maps APIs
    ├── spanner/             # Cloud Spanner instance, databases, and BigQuery connections
    ├── storage/             # GCS artifacts bucket
    ├── redis/               # MemoryStore Redis and VPC Access connector
    ├── datacommons_services/# Cloud Run serving container (Envoy + Mixer + Website)
    │
    └── ingestion/           # Ingestion pipeline submodules
        ├── preprocessing_job# Cloud Run job executing datacommons-data (dcpbridge mode)
        ├── dataflow/        # Service accounts and IAM for Apache Beam Java Dataflow
        ├── postprocessing_job # Cloud Run job executing aggregation queries
        ├── helper_service/  # FastAPI Cloud Run service managing locks and embeddings
        └── workflow/        # Google Cloud Workflows orchestration definition
```

---

## Next Steps

* **Interactive Onboarding**: Follow [Developer Onboarding Codelab](../../docs/codelabs/dcp_developer_onboarding.md) to deploy, seed, ingest, and tear down an instance.
* **CLI Tooling**: Review [Admin CLI Architecture](../../docs/architecture/admin_cli.md) to understand how the CLI reads Terraform outputs and orchestrates jobs.
* **Database Migrations**: Refer to [Schema Migrations Developer Guide](../../docs/schema_migrations_developer_guide.md) for Spanner schema versioning procedures.
