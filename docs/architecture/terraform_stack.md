# Data Commons Platform Terraform Stack Architecture

## Overview

The Data Commons Platform (DCP) deploys on Google Cloud Platform (GCP) using declarative Infrastructure as Code (IaC) managed by HashiCorp Terraform. 

The infrastructure layer provisions and connects Google Cloud Spanner, Cloud Run services and jobs, Cloud Workflows, Google Cloud Storage (GCS), Secret Manager, MemoryStore for Redis, and Serverless VPC Access connectors.

This document details the dual entrypoint architecture, the central module orchestration topology, the variable propagation pipeline, and critical infrastructure guardrails.

---

## 1. Dual Entrypoint Architecture

DCP supports two distinct deployment workflows: one for external consumers running instances, and one for core platform contributors developing the infrastructure modules.

```
┌────────────────────────────────────────────────────────────────────────┐
│ Consumer Entrypoint (Instance Operators / DCP Admins)                  │
│                                                                        │
│ 1. Operator runs: datacommons admin init --namespace dev-user          │
│ 2. CLI downloads root files (main.tf, variables.tf, outputs.tf)        │
│ 3. CLI rewrites source to remote GitHub release tag                    │
│    source = "git::https://github.com/.../modules/stack?ref=v1.1.2"     │
│ 4. Operator runs terraform init and terraform apply from ~/deployments │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ Contributor Entrypoint (Platform Developers / Core Engineers)          │
│                                                                        │
│ 1. Developer clones datacommonsorg/datacommons repository               │
│ 2. Developer works directly in infra/dcp/                              │
│ 3. main.tf points directly to local filesystem submodules:             │
│    source = "./modules/stack"                                          │
│ 4. Developer runs terraform init and terraform apply locally           │
└────────────────────────────────────────────────────────────────────────┘
```

### The Consumer Entrypoint (`datacommons admin init`)
External administrators and deployment operators use the `datacommons admin init` command. The CLI scaffolds a standalone deployment workspace without requiring a full clone of the monorepo:
1. The CLI fetches `main.tf`, `variables.tf`, `outputs.tf`, and `terraform.tfvars.template` from GitHub for the specified release tag.
2. The CLI executes a regex substitution on line 166 of `main.tf`, converting the local relative path (`source = "./modules/stack"`) into a remote Git reference (`source = "git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref=<tag>"`).
3. The CLI populates user-selected variables (project ID, namespace, API key) into `terraform.tfvars`.
4. The administrator executes `terraform init` and `terraform apply` within their dedicated workspace folder.

### The Contributor Entrypoint (`infra/dcp/`)
Platform contributors modifying Terraform definitions or testing changes work directly inside the `infra/dcp/` directory:
1. Contributors edit configurations across `infra/dcp/` and `infra/dcp/modules/`.
2. The root `infra/dcp/main.tf` references `./modules/stack` directly via local filesystem paths.
3. Contributors test changes against sandbox GCP projects using personal `terraform.tfvars` files.

---

## 2. Stack Orchestration and Module Topology

DCP uses a hierarchical module architecture. Submodules never reference or depend on each other directly. Instead, `infra/dcp/modules/stack/main.tf` serves as the single orchestration hub that passes outputs between submodules and binds cross-module Identity and Access Management (IAM) policies.

```
                            infra/dcp/main.tf
                                    │
                                    ▼
                         modules/stack/main.tf
                       (Central Orchestrator Hub)
      ┌──────────────┬──────────────┼──────────────┬──────────────┐
      │              │              │              │              │
      ▼              ▼              ▼              ▼              ▼
modules/auth   modules/spanner modules/storage modules/redis modules/ingestion/
(Secret Mgr)   (Instance & DB) (GCS Buckets)   (VPC & Cache) ├── preprocessing_job
                                                             ├── dataflow
                                                             ├── postprocessing_job
                                                             ├── helper_service
                                                             └── workflow
```

### Module Responsibilities
* **`modules/auth`**: Provisions Secret Manager secrets for Data Commons and Google Maps API keys.
* **`modules/spanner`**: Manages the Cloud Spanner instance, databases, processing units, retention policies, and BigQuery federated connections.
* **`modules/storage`**: Creates the central artifacts GCS bucket (`gs://<namespace>-dc-artifacts-<project_id>`) for raw input data, intermediate shards, and pipeline handshakes.
* **`modules/redis`**: Provisions a Google Cloud MemoryStore Redis instance and Serverless VPC Access connector for low-latency query caching.
* **`modules/ingestion/`**: Contains submodules for each ingestion stage:
  * `preprocessing_job`: Cloud Run job executing `datacommons-data` in `dcpbridge` mode.
  * `dataflow`: Service accounts, bucket permissions, and IAM policies for Apache Beam Dataflow execution.
  * `postprocessing_job`: Cloud Run job executing `datacommons-aggregation-helper` via BigQuery federated queries.
  * `helper_service`: FastAPI Cloud Run service managing Spanner database locks, version promotion, and Vertex AI embeddings.
  * `workflow`: Google Cloud Workflows orchestrator coordinating the execution pipeline.
* **`modules/datacommons_services`**: Cloud Run serving container hosting Envoy, Mixer, and Website.

### Shared Environment Variables
To keep environment variables uniform across Cloud Run services and jobs, `modules/stack/main.tf` constructs a shared local object: `cloud_run_shared_env_variables`. This block injects:
* `USE_CLOUDSQL = "false"`
* `OUTPUT_DIR = gs://<artifacts_bucket>/<artifacts_path>`
* `REDIS_HOST` and `REDIS_PORT` (populated conditionally if Redis is enabled)
* `GCP_SPANNER_INSTANCE_ID` and `GCP_SPANNER_DATABASE_NAME`
* `PROJECT_ID`, `REGION`, and `WORKFLOW_LOCATION`
* `USE_SPANNER_GRAPH = "true"`

### Cross-Module IAM Wiring
Decoupling submodules requires that all cross-service permissions reside in `modules/stack/main.tf`:
1. **GCS Storage Access**:
   * Grants `roles/storage.objectAdmin` on the artifacts bucket to the Dataflow service account, the Workflow service account, and the Preprocessing Job service account.
2. **Workflow Job Invocation**:
   * Grants the Cloud Workflows service account `roles/run.invoker`, `roles/run.viewer`, and `roles/run.developer` on both the Preprocessing and Postprocessing Cloud Run jobs.
   * Grants the Cloud Workflows service account `roles/iam.serviceAccountUser` on the Preprocessing and Postprocessing service accounts so Workflows can execute jobs as those identities.
3. **Workflow Dataflow Control**:
   * Grants `roles/dataflow.developer` to the Cloud Workflows service account.
4. **Service Rolling Restarts**:
   * Grants `roles/run.developer` and `roles/iam.serviceAccountUser` over `datacommons-services` to the Cloud Workflows service account, allowing the workflow to patch serving labels and trigger rolling container restarts upon successful ingestion.

---

## 3. Variable Propagation Pipeline and Naming Conventions

To keep configurations clean and predictable across dozens of resources, DCP enforces a strict variable propagation pipeline and standardized resource naming rules.

### The Propagation Pipeline
Variables flow downward through four stages:

```
Stage 1: User Configuration
User sets prefixed root variable in terraform.tfvars
e.g. spanner_create_instance = false, spanner_instance_id = "dcp-testing"
                       │
                       ▼
Stage 2: Root Aggregation (infra/dcp/main.tf)
Root aggregates individual variables into typed local configuration objects:
local.spanner_config = {
  create_instance = var.spanner_create_instance
  instance_id     = var.spanner_instance_id
  ...
}
                       │
                       ▼
Stage 3: Stack Interface (infra/dcp/modules/stack/variables.tf)
The stack orchestrator accepts the structured object:
variable "spanner_config" {
  type = object({
    create_instance = bool
    instance_id     = string
    ...
  })
}
                       │
                       ▼
Stage 4: Submodule Invocation (modules/stack/main.tf -> modules/spanner/)
The stack module unpacks the object into short, module-scoped variable names:
module "spanner" {
  source          = "../spanner"
  create_instance = var.spanner_config.create_instance
  instance_id     = var.spanner_config.instance_id
}
```

### Naming Conventions
1. **Root Variables (`infra/dcp/variables.tf`)**:
   * Feature toggles follow `enable_<component>` (such as `enable_redis`, `enable_spanner`).
   * Component variables use prefixes to avoid namespace collisions (such as `spanner_instance_id`, `redis_memory_size_gb`, `ingestion_dataflow_max_workers`).
   * Resource creation toggles use `<component>_create_<resource>` (such as `spanner_create_instance`, `spanner_create_database`, `storage_create_artifacts_bucket`).
2. **Submodule Variables (`infra/dcp/modules/<component>/variables.tf`)**:
   * Strip component prefixes inside submodules. Use `create_instance` instead of `spanner_create_instance`, and `memory_size_gb` instead of `redis_memory_size_gb`.
3. **GCP Resource Names**:
   * All provisioned resources follow the pattern: `${local.name_prefix}dc-[functional-name]`.
   * `local.name_prefix` evaluates to `"${var.namespace}-"` when a namespace is provided, or an empty string when omitted.
   * Examples:
     * Spanner instance: `dc-instance` (or `dev-alice-dc-instance`)
     * Spanner database: `dc-db`
     * Storage bucket: `dev-alice-dc-artifacts-datcom-website-dev`
     * Serving service: `dev-alice-dc-datacommons-service`
     * Cloud Workflow: `dev-alice-dc-ingestion-workflow`

---

## 4. Infrastructure Guardrails and Operational Gotchas

Deploying DCP on Google Cloud involves specific account and service constraints. Understanding these rules prevents deployment failures and data loss.

### 1. BigQuery Reservation Quota Limits
* Google Cloud enforces a strict quota of **one BigQuery slot reservation per project per region**.
* If multiple engineers deploy private development instances into the same GCP project (for example, `datcom-website-dev` in `us-central1`), only the first instance can create a reservation.
* Secondary deployments attempting to create a reservation fail with a resource collision error.
* **Resolution**: When sharing a GCP project, set `spanner_create_bigquery_reservation = false` in `terraform.tfvars`. BigQuery postprocessing queries will execute using standard on-demand compute slots.

### 2. Stateful vs Stateless Deletion Protection
DCP separates deletion protection into two independent variables in `infra/dcp/variables.tf`:
* **`stateful_deletion_protection`** (defaults to `true`): Protects data storage layers, including Cloud Spanner databases, instances, and GCS storage buckets. Prevents accidental destruction during automated cleanups.
* **`stateless_deletion_protection`** (defaults to `false`): Controls compute resources like Cloud Run services, Cloud Run jobs, and Cloud Workflows. Allows quick teardown and redeployment of compute targets.
* Before running `terraform destroy` on an experimental instance, operators must explicitly set `stateful_deletion_protection = false` in `terraform.tfvars` and run `terraform apply` first to unlock the stateful resources.

### 3. Service Account Token Creator Requirement
* Cloud Workflows, Cloud Run jobs, and the `datacommons admin init-db` CLI command run under dedicated service account identities.
* To execute the workflow or trigger database schema initialization, the deploying developer or CI runner requires permission to impersonate the workflow orchestrator service account.
* If missing, the developer must grant `roles/iam.serviceAccountTokenCreator` on the workflow service account to their identity:
  ```bash
  gcloud iam service-accounts add-iam-policy-binding <workflow-sa-email> \
      --member="user:<username>@google.com" \
      --role="roles/iam.serviceAccountTokenCreator" \
      --project=<project-id>
  ```
