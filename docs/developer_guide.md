# Data Commons Platform Developer Guide

## Overview

Welcome to the Data Commons Platform (DCP) developer guide. This document serves as the day-to-day workbench manual for engineers developing, testing, and debugging code within the `datcom-datacommons` monorepo.

* **Looking for the PR process and contribution checklist?** Refer to [CONTRIBUTING.md](../CONTRIBUTING.md).
* **New to DCP and want to deploy a test instance on GCP?** Follow the [Developer Onboarding Codelab](codelabs/dcp_developer_onboarding.md).
* **Looking for platform architecture and data flows?** Read [Platform Architecture](architecture/platform_architecture.md).

---

## 1. Monorepo Topology and `uv` Workspace

This repository is structured as a Python monorepo managed by [uv](https://docs.astral.sh/uv/), alongside Terraform infrastructure configurations and integration test suites.

```
datcom-datacommons/
├── packages/                            # Python monorepo packages managed via uv
│   ├── datacommons-cli/                 # User-facing CLI entrypoint (datacommons)
│   ├── datacommons-admin/               # Administrative logic, scaffolding, and cloud clients
│   ├── datacommons-db/                  # Database models, Spanner client (DCGraph), migrations
│   ├── datacommons-schema/              # Pydantic models for JSON-LD and MCF parsing
│   └── datacommons-api/                 # API service layer components
│
├── infra/
│   └── dcp/                             # Terraform modules for provisioning GCP infrastructure
│       ├── main.tf                      # Root Terraform configuration
│       ├── variables.tf                 # Root variable definitions
│       ├── terraform.tfvars.template    # Configuration template for deployments
│       └── modules/                     # Submodules (spanner, storage, auth, ingestion, etc.)
│
├── docs/                                # Centralized platform documentation
│   ├── README.md                        # Documentation blueprint and directory index
│   ├── developer_guide.md               # This document (workbench manual)
│   ├── user_guide.md                    # Master operational manual for DCP Admins
│   ├── codelabs/                        # Hands-on interactive tutorials
│   └── architecture/                    # Technical deep dives and specifications
│
├── tests/                               # Integration tests and automated cloud probers
│   └── integration/                     # Hermetic Docker Compose test suite and GCP testbed
│
└── experimental/                        # Experimental tools and artifact build scripts
```

### Monorepo Packages Breakdown

| Package Path | Package Name | Responsibility |
| :--- | :--- | :--- |
| `packages/datacommons-cli` | `datacommons-cli` | Thin distribution wrapper that exposes the `datacommons` console script and routes subcommands. Published to PyPI. |
| `packages/datacommons-admin` | `datacommons-admin` | Core administrative logic: template downloading for `admin init`, Spanner migration triggers for `admin init-db`, and Cloud Workflows API integration for `admin ingest start`. Published to PyPI. |
| `packages/datacommons-db` | `datacommons-db` | Database layer containing SQLAlchemy models, the `DCGraph` Spanner client, and versioned migration DDL scripts in `migration_scripts/`. Published to PyPI. |
| `packages/datacommons-schema` | `datacommons-schema` | Graph schema data models and format converters between MCF and compact JSON-LD *(unpublished prototype)*. |
| `packages/datacommons-api` | `datacommons-api` | Internal API endpoints and service interfaces *(unpublished prototype)*. |

> [!NOTE]
> **Unpublished Prototype Packages**: `packages/datacommons-schema` and `packages/datacommons-api` are not published to PyPI. They represent initial architecture explorations that the team pivoted away from, preserved in the workspace for potential future reuse. Only `datacommons-cli`, `datacommons-admin`, and `datacommons-db` are actively built, versioned, and published.

### How `uv Workspace` Works
The repository root defines a unified workspace in `pyproject.toml`:
```toml
[tool.uv.workspace]
members = [
    "packages/*",
    "tools",
]
```
When you run commands using `uv`, all member packages are installed into a single shared virtual environment located at `.venv/` in editable mode. Any changes you make to `packages/datacommons-admin/` or `packages/datacommons-db/` take effect immediately without requiring reinstallation.

### Managing Package Dependencies
Always scope dependency additions to the specific package:
```bash
# Add a runtime dependency to datacommons-admin
uv add --package datacommons-admin <dependency-name>

# Add a development dependency to the root workspace
uv add --dev <dependency-name>
```

---

## 2. Local Development Recipes (The Workbench)

### Working on the CLI (`datacommons-cli` & `datacommons-admin`)

#### 1. Running Local CLI Code in Editable Mode
To run unreleased CLI code directly from your working tree without installing the package globally, use `uv run --package datacommons-cli`:

```bash
# Run admin init using local code
uv run --package datacommons-cli datacommons admin init

# Run database setup against an existing deployment
uv run --package datacommons-cli datacommons admin init-db

# Trigger data ingestion using local logic
uv run --package datacommons-cli datacommons admin ingest start --imports <dataset_name>
```

#### 2. Adding a New CLI Command
1. Define the Click command in `packages/datacommons-admin/datacommons_admin/<group>/<group>_cli.py`.
2. Register the command on the group in `packages/datacommons-admin/datacommons_admin/admin_cli.py`.
3. If the command reads Terraform attributes, fetch them via `tf_utils.get_terraform_outputs()`.
4. Ensure any new output keys added to `infra/dcp/outputs.tf` match fields in the `TerraformOutputs` dataclass (`packages/datacommons-admin/datacommons_admin/core/utils/models.py`). Run the contract test to verify parity:
   ```bash
   uv run pytest packages/datacommons-admin/tests/core/test_tf_contract.py
   ```

### Working on the Database Layer (`datacommons-db`)

1. **Entity Models**: Graph models (`NodeRecord`, `EdgeRecord`, `ObservationRecord`, `TimeSeriesRecord`) reside in `packages/datacommons-db/datacommons_db/models/`.
2. **Schema Migrations**: Schema alterations are managed as versioned Python migration scripts in `packages/datacommons-db/datacommons_db/migrations/migration_scripts/`.
   * For instructions on authoring, naming, and testing migrations, consult the [Schema Migrations Developer Guide](schema_migrations_developer_guide.md).

### Working on Infrastructure (`infra/dcp`)

When modifying Terraform configurations in `infra/dcp/`:
1. **Module Hierarchy**: Inspect `infra/dcp/main.tf` for root variables and `infra/dcp/modules/stack/main.tf` for module wiring. Refer to [Terraform Stack Architecture](architecture/terraform_stack.md) for variable propagation details.
2. **Critical Scaffolding Contract**: The `module "stack"` declaration in `infra/dcp/main.tf` must maintain `source = "./modules/stack"` on a single line:
   ```hcl
   module "stack" {
     source = "./modules/stack"
   ```
   The `datacommons admin init` CLI command uses regular expression matching on `source = "./modules/stack"` to rewrite the module source to the remote GitHub release URL for downstream users. Modifying line breaks or whitespace within this string breaks CLI scaffolding.
3. **Local Validation and Pre-Flight Checks**: Validate and test Terraform changes by copying `infra/dcp/terraform.tfvars.template` to `infra/dcp/terraform.tfvars` and running:
   ```bash
   cd infra/dcp

   # Check file formatting
   terraform fmt -check

   # Initialize providers and modules
   terraform init

   # Validate configuration syntax and internal consistency
   terraform validate

   # Generate execution plan against your project
   terraform plan
   ```
4. **Testing Local Module Changes in a Scaffolded Workspace**:
   When testing changes to `infra/dcp/modules/` inside a personal deployment directory created by `admin init` without having to push commits to a remote Git branch:
   * **Option A (Direct Local Path)**: In your deployment's `main.tf`, replace the remote Git reference with your local monorepo path:
     ```hcl
     module "stack" {
       source = "/absolute/path/to/datcom-datacommons/infra/dcp/modules/stack"
     ```
   * **Option B (Local Symlink)**: Create a symlink inside your deployment folder pointing to the local `modules` directory:
     ```bash
     ln -s /absolute/path/to/datcom-datacommons/infra/dcp/modules ./modules
     ```
     Then point `main.tf` to the local symlink:
     ```hcl
     module "stack" {
       source = "./modules/stack"
     ```
   * **Re-Initialize and Plan**:
     ```bash
     terraform init -upgrade
     terraform plan
     ```
     Terraform switches from pulling remote Git objects to reading your live local workspace directly. Any edits made in `infra/dcp/modules/` immediately take effect on the next plan or apply.
5. **Testing Against DCP Versions vs. Head**:
   The `dcp_version` variable in `terraform.tfvars` governs container images and Dataflow templates:
   * **Testing Against Head (Latest `main`)**:
     ```hcl
     dcp_version = "latest"
     ```
     In `infra/dcp/modules/stack/main.tf`, `FORCE_RESTART = timestamp()` ensures Cloud Run pulls the newest `:latest` image digest on each `terraform apply`, and points Dataflow to the `stable` Flex Template.
   * **Testing Against a Specific Released Version (e.g. `v1.1.2`, `1.1.3rc1`)**:
     ```hcl
     dcp_version = "v1.1.2"
     ```
     Pins all four Cloud Run container images (`datacommons-services`, `datacommons-data`, `datacommons-aggregation-helper`, `datacommons-ingestion-helper`) to that exact tag.
   * **Testing Custom Development Container Images**:
     To test custom container builds before tagging or publishing, override individual container variables directly in `terraform.tfvars`:
     ```hcl
     datacommons_services_image = "gcr.io/datcom-ci/datacommons-services:dev-username"
     ```

### Working with Container Images (Building & Overriding)

DCP microservices execute in serverless Google Cloud Run containers. The images originate from multiple repositories across the Data Commons ecosystem:

| Container Image | Component Role | Source Repository & Dockerfile | Destination Registry (Dev) | `terraform.tfvars` Override |
| :--- | :--- | :--- | :--- | :--- |
| **`datacommons-services`** | Envoy, Mixer API, Website serving | `datcom-website`<br>`cloudbuild-services-dev.yaml` | `gcr.io/datcom-website-dev/datacommons-services:<tag>` | `datacommons_services_image` |
| **`datacommons-data`** | Preprocessor batch job | `datcom-website`<br>`build/cdc_data/Dockerfile` | `us-docker.pkg.dev/datcom-website-dev/datacommons-artifacts/datacommons-data:<tag>` | `ingestion_preprocessing_job_image` |
| **`datacommons-aggregation-helper`** | Postprocessor aggregation job | `datcom-import`<br>`pipeline/workflow/aggregation-helper/Dockerfile` | `gcr.io/datcom-website-dev/datacommons-aggregation-helper:<tag>` | `ingestion_postprocessing_job_image` |
| **`datacommons-ingestion-helper`** | Lock coordination & migrations | `datcom-import`<br>`pipeline/workflow/ingestion-helper/Dockerfile` | `us-docker.pkg.dev/datcom-website-dev/datacommons-artifacts/ingestion-helper:<tag>` | `ingestion_helper_service_image` |

#### 1. Submodule Alignment (Before Building `services` or `data` Images)
The `datcom-website` repository incorporates `mixer` and `import` as Git submodules. If your changes involve code inside Mixer or Import:
1. Navigate into the submodule directory inside `datcom-website`:
   ```bash
   cd /path/to/datcom-website/mixer
   git checkout <target_branch_or_commit>
   ```
2. Return to the root of `datcom-website` and confirm that `git status` displays the updated submodule commit pointer before submitting the build.

#### 2. Building Images via Google Cloud Build
Build custom container images and push them to Google Container Registry (GCR) or Artifact Registry in the development project (`datcom-website-dev`):

* **Serving Services (`datacommons-services`)**:
  ```bash
  cd /path/to/datcom-website
  gcloud builds submit . \
      --project=datcom-website-dev \
      --config=cloudbuild-services-dev.yaml \
      --substitutions=_TAG=<custom_tag>
  ```
* **Preprocessor (`datacommons-data`)**:
  ```bash
  cd /path/to/datcom-website
  export PREPROCESSOR_IMAGE="us-docker.pkg.dev/datcom-website-dev/datacommons-artifacts/datacommons-data:<custom_tag>"
  gcloud builds submit --project=datcom-website-dev --tag "$PREPROCESSOR_IMAGE" -f build/cdc_data/Dockerfile .
  ```
* **Postprocessor (`datacommons-aggregation-helper`)**:
  ```bash
  cd /path/to/datcom-import/pipeline/workflow/aggregation-helper
  gcloud builds submit . \
      --project=datcom-website-dev \
      --tag="gcr.io/datcom-website-dev/datacommons-aggregation-helper:<custom_tag>"
  ```
* **Ingestion Helper Service (`ingestion-helper`)**:
  ```bash
  cd /path/to/datcom-import
  export INGESTION_HELPER_IMAGE="us-docker.pkg.dev/datcom-website-dev/datacommons-artifacts/ingestion-helper:<custom_tag>"
  gcloud builds submit --project=datcom-website-dev --tag "$INGESTION_HELPER_IMAGE" -f pipeline/workflow/ingestion-helper/Dockerfile .
  ```

#### 3. Overriding Images in `terraform.tfvars`
To test your custom container image on your deployed DCP instance, override the respective image variable in `~/dcp-deployments/<namespace>/terraform.tfvars`:

```hcl
# Custom container image overrides
datacommons_services_image         = "gcr.io/datcom-website-dev/datacommons-services:<custom_tag>"
ingestion_preprocessing_job_image  = "us-docker.pkg.dev/datcom-website-dev/datacommons-artifacts/datacommons-data:<custom_tag>"
ingestion_postprocessing_job_image = "gcr.io/datcom-website-dev/datacommons-aggregation-helper:<custom_tag>"
ingestion_helper_service_image      = "us-docker.pkg.dev/datcom-website-dev/datacommons-artifacts/ingestion-helper:<custom_tag>"
```

Apply the updated configuration:
```bash
cd ~/dcp-deployments/<namespace>
terraform plan -out=tfplan
terraform apply tfplan
```

Terraform updates the Cloud Run service or job definition to reference your custom image URI and deploys a new revision without modifying persistent storage layers or Spanner databases.

---

## 3. Testing Strategy and Execution

DCP enforces a two-tier testing hierarchy with clear division of responsibilities:

* **Unit Tests (Mandatory for all contributions)**: Fast, lightweight, in-memory tests running via `pytest`. All external network services, cloud APIs (Cloud Spanner, Cloud Workflows, Cloud Storage), and shell calls are mocked. Unit tests execute in seconds, run automatically in pre-submit CI, and are required for every bug fix, feature, and CLI subcommand.
* **Hermetic Integration Tests (End-to-End Validation)**: Local multi-service testing using Docker Compose to emulate Cloud Spanner, Cloud Storage, and serving containers. Integration tests validate end-to-end data ingestion, schema migrations, and live query resolution without incurring GCP cloud costs. They are heavier and slower than unit tests, primarily run before cutting releases or verifying cross-cutting data pipelines.

### 1. Unit Tests
Run unit tests across all monorepo packages using `pytest`:

```bash
# Run all unit tests in the repository
uv run pytest

# Run tests scoped to a single package
uv run pytest packages/datacommons-admin/tests/
uv run pytest packages/datacommons-db/tests/
```

### 2. Hermetic Integration Tests
The repository includes a hermetic testbed that uses Docker Compose to emulate Cloud Spanner, Cloud Storage, Ingestion Helper, and serving containers locally without incurring GCP cloud costs:

```bash
uv run pytest tests/integration/suites/ \
    --instance local \
    --test-config foobar_wages
```

> **Single Source of Truth**: For complete details on Docker Compose emulation, developer fast-iteration flags (such as `--reuse-data` to skip re-ingestion), and running tests against live GCP sandbox projects, refer to the [Integration Tests Guide](../tests/integration/README.md).

---

## 4. Debugging Workflows and Common Gotchas

### 1. Missing `DC_API_KEY`
* **Symptom**: Integration tests or local serving queries fail with unauthorized or upstream RPC errors.
* **Resolution**: DCP federates queries against base Google Data Commons. Obtain a key from [apikeys.datacommons.org](https://apikeys.datacommons.org) and ensure `DC_API_KEY` is exported in your shell:
  ```bash
  export DC_API_KEY="your-api-key"
  ```

### 2. BigQuery Reservation Collision
* **Symptom**: `terraform apply` fails with an error indicating that a BigQuery slot reservation already exists in the project and region.
* **Resolution**: Google Cloud allows only one BigQuery slot reservation per project per region. When sharing a development project (such as `datcom-website-dev`), set `spanner_create_bigquery_reservation = false` in your `terraform.tfvars`.

### 3. Spanner Emulator Port Conflicts
* **Symptom**: Hermetic integration tests report `Address already in use` on port 9010 or 9020.
* **Resolution**: Ensure no previous Docker Compose test containers are running:
  ```bash
  docker compose -f tests/integration/emulated/docker-compose.yml down -v
  ```

### 4. Service Account Token Creator Missing
* **Symptom**: `datacommons admin init-db` or `datacommons admin ingest start` fails with HTTP 403 / IAM permission denied when acquiring credentials.
* **Resolution**: Ensure your GCP user account has `roles/iam.serviceAccountTokenCreator` on the workflow service account:
  ```bash
  gcloud iam service-accounts add-iam-policy-binding <workflow-sa-email> \
      --member="user:$(gcloud config get-value account)" \
      --role="roles/iam.serviceAccountTokenCreator" \
      --project=<project-id>
  ```
