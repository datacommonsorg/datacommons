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

---

## Configuration Reference (`terraform.tfvars`)

The table below documents variables configured in `terraform.tfvars.template`.

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `project_id` | `string` | *(required)* | Target Google Cloud Project ID. |
| `instance_name` | `string` | *(required)* | Unique namespace prefix for provisioned GCP resources (such as `dev-alice`). Maximum 16 lowercase alphanumeric characters and hyphens. |
| `region` | `string` | `"us-central1"` | Primary GCP compute and storage region. |
| `stateful_deletion_protection` | `bool` | `false` in template (`true` in schema) | Prevents accidental deletion of persistent storage layers (Cloud Spanner databases and GCS storage buckets). Set to `true` in production. |
| `stateless_deletion_protection` | `bool` | `false` | Controls deletion protection on Cloud Run services, Cloud Run jobs, and Cloud Workflows. Keep `false` for rapid development updates. |
| `auth_google_datacommons_api_key` | `string` | *(required)* | Data Commons API Key from [apikeys.datacommons.org](https://apikeys.datacommons.org). Required for base knowledge graph federation. |
| `storage_create_artifacts_bucket` | `bool` | `true` | When `true`, provisions a dedicated GCS bucket: `<instance_name>-dc-artifacts-<project_id>`. Set to `false` when reusing an existing bucket. |
| `storage_artifacts_bucket_name` | `string` | `null` | Name of existing GCS bucket if `storage_create_artifacts_bucket = false`. |
| `enable_redis` | `bool` | `false` | When `true`, provisions a Google Cloud MemoryStore Redis instance and Serverless VPC Access connector for low-latency query caching. |
| `spanner_create_instance` | `bool` | `true` | When `true`, provisions a dedicated Spanner instance. Set to `false` to reuse an existing instance (such as shared `dcp-testing`). |
| `spanner_instance_id` | `string` | `""` | Target Spanner instance ID when `spanner_create_instance = false`. |
| `spanner_create_database` | `bool` | `true` | Provisions `<instance_name>-dc-db` inside the Spanner instance. |
| `spanner_create_bigquery_reservation` | `bool` | `true` | Provisions a dedicated BigQuery slot commitment for Spanner federated queries. **Constraint**: GCP limits projects to one reservation per region. Set to `false` in shared development projects. |
| `datacommons_services_allow_unauthenticated_access` | `bool` | `false` | When `false`, Cloud Run requires IAM credentials. When `true`, exposes public HTTPS traffic. |
| `ingestion_input_path` | `string` | `"ingestion/input"` | Root directory inside the artifacts bucket where raw dataset folders are staged. |

---

## Deployment Outputs

Run `terraform output` to retrieve provisioned infrastructure attributes.

| Output Name | Description |
| :--- | :--- |
| `project_id` | The GCP project ID hosting the deployment. |
| `region` | The GCP region where resources are deployed. |
| `spanner_instance_id` | Active Cloud Spanner instance ID. |
| `spanner_database_id` | Provisioned Cloud Spanner database ID (`<instance_name>-dc-db`). |
| `storage_artifacts_bucket_name` | Name of the provisioned or referenced GCS artifacts bucket. |
| `ingestion_input_path` | GCS prefix where dataset input folders are uploaded. |
| `datacommons_service_name` | Name of the `datacommons-services` Cloud Run service. |
| `datacommons_service_url` | HTTPS endpoint of the serving service. |
| `datacommons_service_service_account_email` | Service account identity used by the serving container. |
| `ingestion_workflow_name` | Name of the Google Cloud Workflows orchestrator. |
| `ingestion_workflow_id` | Resource ID of the Cloud Workflows orchestrator. |
| `ingestion_workflow_service_account_email` | Service account identity used by the ingestion workflow. |
| `ingestion_service_url` | HTTPS endpoint of the `datacommons-ingestion-helper` Cloud Run service. |
| `ingestion_prep_job_name` | Name of the `datacommons-data` preprocessing Cloud Run job. |

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
