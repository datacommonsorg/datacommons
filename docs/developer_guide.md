# Data Commons Platform Developer Guide

## Overview

Welcome to the Data Commons Platform (DCP) developer guide. This document serves as the day-to-day workbench manual for engineers developing, testing, and debugging code within the `datcom-datacommons` monorepo.

* **Looking for the PR process and contribution checklist?** Refer to [CONTRIBUTING.md](../CONTRIBUTING.md).
* **New to DCP and want to deploy a test instance on GCP?** Follow the [Developer Onboarding Codelab](codelabs/dcp_developer_onboarding.md).
* **Looking for platform architecture and data flows?** Read [Platform Architecture](architecture/platform_architecture.md).

---

## Monorepo Topology and `uv` Workspace

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
│   ├── README.md                        # Documentation architecture and standards
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

## Local Development Recipes (The Workbench)

### Working on the CLI (`datacommons-cli` and `datacommons-admin`)

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

#### Adding a New CLI Command
* Define the Click command in `packages/datacommons-admin/datacommons_admin/<group>/<group>_cli.py`.
* Register the command on the group in `packages/datacommons-admin/datacommons_admin/admin_cli.py`.
* If the command reads Terraform attributes, fetch them via `tf_utils.get_terraform_outputs()`.
* Ensure any new output keys added to `infra/dcp/outputs.tf` match fields in the `TerraformOutputs` dataclass (`packages/datacommons-admin/datacommons_admin/core/utils/models.py`). Run the contract test to verify parity:
  ```bash
  uv run pytest packages/datacommons-admin/tests/core/test_tf_contract.py
  ```

### Working on the Database Layer (`datacommons-db`)

* **Entity Models**: Graph models (`NodeRecord`, `EdgeRecord`, `ObservationRecord`, `TimeSeriesRecord`) reside in `packages/datacommons-db/datacommons_db/models/`.
* **Schema Migrations**: Schema alterations are managed as versioned Python migration scripts in `packages/datacommons-db/datacommons_db/migrations/migration_scripts/`.
  * For instructions on authoring, naming, and testing migrations, consult the [Schema Migrations Developer Guide](schema_migrations_developer_guide.md).

### Working on Infrastructure (`infra/dcp`)

When modifying Terraform configurations in `infra/dcp/`:
* **Module Hierarchy**: Inspect `infra/dcp/main.tf` for root variables and `infra/dcp/modules/stack/main.tf` for module wiring. Refer to [Terraform Stack Architecture](architecture/terraform_stack.md) for variable propagation details.
* **Critical Scaffolding Contract**: The `module "stack"` declaration in `infra/dcp/main.tf` must maintain `source = "./modules/stack"` on a single line:
  ```hcl
  module "stack" {
    source = "./modules/stack"
  ```
  The `datacommons admin init` CLI command uses regular expression matching on `source = "./modules/stack"` to rewrite the module source to the remote GitHub release URL for downstream users. Modifying line breaks or whitespace within this string breaks CLI scaffolding.
* **Local Validation and Pre-Flight Checks**: Validate and test Terraform changes by copying `infra/dcp/terraform.tfvars.template` to `infra/dcp/terraform.tfvars` and running:
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
* **Testing Local Module Changes in a Scaffolded Workspace**:
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

### Running the Stack on Latest (`main` and `latest` Builds)

When testing cross-repository features or validating unreleased changes against active development branches, deploy your instance against head builds (`main` branch and `:latest` containers) instead of pinned releases.

Running on latest involves four platform layers:

* **Terraform Infrastructure Modules (`main` branch)**:
  In `~/dcp-deployments/<namespace>/main.tf`, point the root stack module to the `main` branch of `datcom-datacommons` (or use a local symlink to `infra/dcp/modules/stack`):
  ```hcl
  module "stack" {
    source = "git::https://github.com/datacommonsorg/datcom-datacommons.git//infra/dcp/modules/stack?ref=main"
  }
  ```

* **Platform Containers & Dataflow Flex Template (`dcp_version = "latest"`)**:
  In `~/dcp-deployments/<namespace>/terraform.tfvars`, set `dcp_version` to `latest`:
  ```hcl
  dcp_version = "latest"
  ```
  Setting `dcp_version = "latest"` activates two runtime behaviors:
  * **Container Image Resolution**: Pins all four Cloud Run services and jobs (`datacommons-services`, `datacommons-data`, `datacommons-aggregation-helper`, `datacommons-ingestion-helper`) to the `:latest` tag in Container Registry (`gcr.io/datcom-ci/...:latest`).
  * **Cache-Busting Image Pulls (`FORCE_RESTART`)**: Google Cloud Run resolves image tags to SHA-256 digests at deployment definition update time, not at request time. In `infra/dcp/modules/stack/main.tf`, setting `FORCE_RESTART = timestamp()` ensures that each `terraform apply` forces Cloud Run to pull the newest `:latest` image digest.
  * **Dataflow Flex Template**: Directs the ingestion pipeline to the unpinned stable Beam template (`gs://datcom-templates/templates/flex/ingestion-stable.json`).

* **Admin CLI on Latest**:
  Run the CLI against the latest `main` branch either on-the-fly via `uvx` or through an editable local installation:
  * **Option A (`uvx` pointing to `main`)**:
    Execute the latest CLI directly from GitHub without installing packages globally:
    ```bash
    uvx --no-cache --from "git+https://github.com/datacommonsorg/datcom-datacommons.git@main#subdirectory=packages/datacommons-cli" datacommons admin <command>
    ```
    > [!NOTE]
    > If scaffolding a new deployment workspace with `admin init` while running against `main`, pass `--tf-git-ref main` (or manually set `?ref=main` in `main.tf`). By default, `admin init` pins the Terraform module source in `main.tf` to the released version tag (such as `v1.1.2`).
  * **Option B (Editable local clone)**:
    Install the package in editable mode from your local checkout:
    ```bash
    cd /path/fork/of/datacommonsorg/datcom-datacommons/packages/datacommons-admin
    pip install -e .
    ```

* **Applying Latest Updates**:
  Pull updated module commits and apply the plan:
  ```bash
  cd ~/dcp-deployments/<namespace>
  terraform init -upgrade
  terraform plan -out=tfplan
  terraform apply tfplan
  ```

### Working with Container Images (Building and Overriding)

DCP microservices and batch pipelines run in serverless Google Cloud Run containers and Cloud Dataflow Apache Beam workers. The images originate from multiple repositories across the Data Commons ecosystem:

* For high-level container topology, container roles, and end-to-end data flows, refer to [Platform Architecture](architecture/platform_architecture.md#container-images-and-gcp-compute-topology).
* For the automated release candidate tagging, promotion, and publishing pipelines, refer to the [Release Guide](release.md).
* This section serves as the developer workbench guide for building custom development containers from source and overriding them in your deployment workspace.

> [!CAUTION]
> **Protected CI/CD Tags Rule**: Never build, push, or overwrite tags that are reserved for CI/CD or platform automation, such as `:latest`, `:stable`, or version release tags (such as `v1.1.2` or `1.1.3rc1`). Overwriting these tags corrupts automated integration tests, release candidate staging, and production deployments. Always use a descriptive, user-scoped tag for development builds (for example, `<username>-<feature>` or `<username>-test-$(date +%s)`).

#### Platform Container and Template Inventory

| Component Name | Role | Source Repo & Dockerfile | Destination Registry (Dev) | `terraform.tfvars` Override |
| :--- | :--- | :--- | :--- | :--- |
| **`datacommons-services`** | Envoy, Mixer API, Website serving | `datcom-website`<br>`scripts/push_cdc_services_image.sh` | `gcr.io/<project_id>/datacommons-services:<tag>` | `datacommons_services_image` |
| **`datacommons-data`** | Preprocessor batch job | `datcom-website`<br>`build/cdc_data/Dockerfile` | `us-docker.pkg.dev/<project_id>/<repository>/datacommons-data:<tag>` | `ingestion_preprocessing_job_image` |
| **`datacommons-aggregation-helper`** | Postprocessor aggregation job | `datcom-import`<br>`pipeline/workflow/aggregation-helper/Dockerfile` | `gcr.io/<project_id>/datacommons-aggregation-helper:<tag>` | `ingestion_postprocessing_job_image` |
| **`datacommons-ingestion-helper`** | Lock coordination & migrations | `datcom-import`<br>`pipeline/workflow/ingestion-helper/Dockerfile` | `us-docker.pkg.dev/<project_id>/<repository>/ingestion-helper:<tag>` | `ingestion_helper_service_image` |
| **`ingestion-flex`** | Apache Beam Dataflow pipeline | `datcom-import`<br>`pipeline/ingestion/Dockerfile` | `us-docker.pkg.dev/<project_id>/<repository>/dataflow-templates/ingestion:<tag>`<br>`gs://<storage_artifacts_bucket_name>/templates/flex/ingestion-<tag>.json` | `ingestion_dataflow_template_gcs_path` |

#### Building Images via Google Cloud Build

Build custom container images and push them to Google Container Registry (GCR) or Artifact Registry:

##### Serving Services (`datacommons-services`)
The `website` repository incorporates `mixer` and `import` as Git submodules. If your changes involve code inside Mixer or Import, align the submodules before triggering the build:

```bash
cd /path/fork/of/datacommonsorg/website

# (Optional) Align submodules:
# Option A: Checkout specific feature branches:
cd mixer && git checkout <mixer_feature_branch> && cd ..
cd import && git checkout <import_feature_branch> && cd ..

# Option B: Sync submodules with upstream master:
git submodule update --remote --merge

# Build and push custom datacommons-services image to development project:
export PROJECT_ID="datcom-website-dev"
export SERVICES_TAG="<username>-<feature>-$(date +%s)"
./scripts/push_cdc_services_image.sh "$SERVICES_TAG" "$PROJECT_ID"

# Resulting Image URI:
# gcr.io/$PROJECT_ID/datacommons-services:<SERVICES_TAG>
```

> [!NOTE]
> `scripts/push_cdc_services_image.sh` invokes `build/ci/cloudbuild.push_cdc_services_image.yaml`, which resolves Git commit hashes for submodules and tags the container image. The second argument specifies the destination GCP project (`$PROJECT_ID`). If omitted, it defaults to the shared `datcom-ci` project (`gcr.io/datcom-ci/datacommons-services:<SERVICES_TAG>`). Images in both registries can be deployed to Cloud Run via `datacommons_services_image` in `terraform.tfvars`.

##### Preprocessor (`datacommons-data`)
```bash
cd /path/fork/of/datacommonsorg/website

# (Optional) Align import submodule:
# Option A: Checkout a specific feature branch:
cd import && git checkout <import_feature_branch> && cd ..

# Option B: Sync import submodule with upstream master:
git submodule update --remote --merge import

# Build and push custom preprocessor image to Artifact Registry:
export PROJECT_ID="datcom-website-dev"
export PREPROCESSOR_TAG="<username>-<feature>-$(date +%s)"
export PREPROCESSOR_IMAGE="us-docker.pkg.dev/$PROJECT_ID/datacommons-artifacts/datacommons-data:$PREPROCESSOR_TAG"
gcloud builds submit --project="$PROJECT_ID" --tag "$PREPROCESSOR_IMAGE" -f build/cdc_data/Dockerfile .

# Resulting Image URI:
# us-docker.pkg.dev/$PROJECT_ID/datacommons-artifacts/datacommons-data:<PREPROCESSOR_TAG>
```

##### Postprocessor (`datacommons-aggregation-helper`)
```bash
cd /path/fork/of/datacommonsorg/import
cd pipeline/workflow/aggregation-helper

export PROJECT_ID="datcom-website-dev"
export POSTPROCESSOR_TAG="<username>-<feature>-$(date +%s)"
gcloud builds submit . \
    --project="$PROJECT_ID" \
    --tag="gcr.io/$PROJECT_ID/datacommons-aggregation-helper:$POSTPROCESSOR_TAG"

# Resulting Image URI:
# gcr.io/$PROJECT_ID/datacommons-aggregation-helper:<POSTPROCESSOR_TAG>
```

##### Ingestion Helper Service (`ingestion-helper`)
```bash
cd /path/fork/of/datacommonsorg/import

export PROJECT_ID="datcom-website-dev"
export INGESTION_HELPER_TAG="<username>-<feature>-$(date +%s)"
export INGESTION_HELPER_IMAGE="us-docker.pkg.dev/$PROJECT_ID/datacommons-artifacts/ingestion-helper:$INGESTION_HELPER_TAG"
gcloud builds submit --project="$PROJECT_ID" --tag "$INGESTION_HELPER_IMAGE" -f pipeline/workflow/ingestion-helper/Dockerfile .

# Resulting Image URI:
# us-docker.pkg.dev/$PROJECT_ID/datacommons-artifacts/ingestion-helper:<INGESTION_HELPER_TAG>
```

##### Dataflow Flex Template and Ingestion Pipeline (`ingestion-flex`)
Dataflow executes as an Apache Beam Java Flex Template. Building it requires packaging the worker container image and staging the template JSON specification in Cloud Storage:

```bash
cd /path/fork/of/datacommonsorg/import

# 1. Build and push custom Dataflow worker image to Artifact Registry:
export PROJECT_ID="datcom-website-dev"
export DATAFLOW_TAG="<username>-<feature>-$(date +%s)"
export DATAFLOW_WORKER_IMAGE="us-docker.pkg.dev/$PROJECT_ID/datacommons-artifacts/dataflow-templates/ingestion:$DATAFLOW_TAG"
gcloud builds submit --project="$PROJECT_ID" --tag "$DATAFLOW_WORKER_IMAGE" -f pipeline/ingestion/Dockerfile .

# 2. Build and stage Dataflow Flex Template JSON specification in Cloud Storage:
export TEMPLATE_GCS_PATH="gs://<storage_artifacts_bucket_name>/templates/flex/ingestion-$DATAFLOW_TAG.json"
gcloud dataflow flex-template build "$TEMPLATE_GCS_PATH" \
    --image "$DATAFLOW_WORKER_IMAGE" \
    --sdk-language "JAVA" \
    --metadata-file "pipeline/ingestion/metadata.json"

# Resulting Worker Image URI:
# us-docker.pkg.dev/$PROJECT_ID/datacommons-artifacts/dataflow-templates/ingestion:<DATAFLOW_TAG>

# Resulting Template GCS Path:
# gs://<storage_artifacts_bucket_name>/templates/flex/ingestion-<DATAFLOW_TAG>.json
```

#### Overriding Images and Templates in `terraform.tfvars`
To test custom container images or Dataflow templates on your deployed DCP instance, override the respective variables in `~/dcp-deployments/<namespace>/terraform.tfvars`:

```hcl
# Custom container image and Dataflow template overrides
datacommons_services_image           = "gcr.io/<project_id>/datacommons-services:<custom_tag>"
ingestion_preprocessing_job_image    = "us-docker.pkg.dev/<project_id>/<repository>/datacommons-data:<custom_tag>"
ingestion_postprocessing_job_image   = "gcr.io/<project_id>/datacommons-aggregation-helper:<custom_tag>"
ingestion_helper_service_image       = "us-docker.pkg.dev/<project_id>/<repository>/ingestion-helper:<custom_tag>"
ingestion_dataflow_template_gcs_path = "gs://<storage_artifacts_bucket_name>/templates/flex/ingestion-<custom_tag>.json"
```

Apply the updated configuration:
```bash
cd ~/dcp-deployments/<namespace>
terraform plan -out=tfplan
terraform apply tfplan
```

Terraform updates the Cloud Run service, job, or Cloud Workflows definition to reference your custom image URI or template path and deploys a new revision without modifying persistent storage layers or Spanner databases.

#### Granting Cross-Project Image Pull Permissions
When building custom container images in a development project (such as `datcom-website-dev`) and deploying them into a DCP instance running in another GCP project (such as `datcom-dcp` testbed environments), the target project's Cloud Run Service Agent must have read access to the source Artifact Registry or Container Registry:

```bash
# Retrieve target project number:
export TARGET_PROJECT_NUM=$(gcloud projects describe <TARGET_PROJECT_ID> --format="value(projectNumber)")

# Option A: Grant Artifact Registry Reader to target Cloud Run Service Agent:
gcloud artifacts repositories add-iam-policy-binding <REPOSITORY_NAME> \
    --location=us \
    --project=<SOURCE_PROJECT_ID> \
    --member="serviceAccount:service-${TARGET_PROJECT_NUM}@serverless-robot-prod.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.reader"

# Option B: Grant Cloud Storage Object Viewer for Google Container Registry (GCR):
gcloud storage buckets add-iam-policy-binding "gs://artifacts.<SOURCE_PROJECT_ID>.appspot.com" \
    --member="serviceAccount:service-${TARGET_PROJECT_NUM}@serverless-robot-prod.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"
```

### Local Workstation IAM Impersonation (Database Seeding and Ingestion)
When executing `datacommons admin init-db`, `admin seed-db`, or `admin ingest start` directly from a local workstation against a deployed instance, the CLI calls the Ingestion Helper service or triggers Google Cloud Workflows using OAuth token impersonation. Before running commands against an instance, grant your user account the `roles/iam.serviceAccountTokenCreator` role on the provisioned Ingestion Workflow Service Account:

```bash
cd ~/dcp-deployments/<namespace>

export MY_USER="$(gcloud config get-value account)"
export PROJECT_ID="$(terraform output -raw project_id)"
export ORCHESTRATOR_SA="$(terraform output -raw ingestion_workflow_service_account_email)"

gcloud iam service-accounts add-iam-policy-binding "$ORCHESTRATOR_SA" \
    --member="user:$MY_USER" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --project="$PROJECT_ID"
```

> [!IMPORTANT]
> Without this IAM binding, the CLI cannot generate OAuth tokens to authenticate with the Cloud Workflows API or Ingestion Helper service, resulting in HTTP 403 Forbidden errors.

### Debugging Private Cloud Run Services Locally
When instances are deployed with `datacommons_services_allow_unauthenticated_access = false` (the secure default), you do not need to make services public or modify IAM policies to test HTTP endpoints. Establish an authenticated local proxy tunnel to the Cloud Run service:

```bash
cd ~/dcp-deployments/<namespace>

export PROJECT_ID="$(terraform output -raw project_id)"
export SERVICE_NAME="$(terraform output -raw datacommons_service_name)"

gcloud run services proxy "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region=us-central1 \
    --port=8080
```

This establishes an encrypted tunnel forwarding `http://localhost:8080` to the private Cloud Run service, automatically attaching your `gcloud` credentials to every request. You can then query endpoints directly via cURL or your browser:

```bash
# Test the V2 Resolve endpoint through the proxy tunnel:
curl -s "http://localhost:8080/core/api/v2/resolve?nodes=california&resolver=place" | jq .

# Test natural language detection and fulfillment:
curl -s -X POST "http://localhost:8080/api/explore/detect-and-fulfill?q=population+in+california" \
    -H "Content-Type: application/json" \
    -d '{}' | jq .
```

---

## Testing Strategy and Execution

DCP enforces a two-tier testing hierarchy with clear division of responsibilities:

* **Unit Tests (Mandatory for all contributions)**: Fast, lightweight, in-memory tests running via `pytest`. All external network services, cloud APIs (Cloud Spanner, Cloud Workflows, Cloud Storage), and shell calls are mocked. Unit tests execute in seconds, run automatically in pre-submit CI, and are required for every bug fix, feature, and CLI subcommand.
* **Hermetic Integration Tests (End-to-End Validation)**: Local multi-service testing using Docker Compose to emulate Cloud Spanner, Cloud Storage, and serving containers. Integration tests validate end-to-end data ingestion, schema migrations, and live query resolution without incurring GCP cloud costs. They are heavier and slower than unit tests, primarily run before cutting releases or verifying cross-cutting data pipelines.

### Unit Tests
Run unit tests across all monorepo packages using `pytest`:

```bash
# Run all unit tests in the repository
uv run pytest

# Run tests scoped to a single package
uv run pytest packages/datacommons-admin/tests/
uv run pytest packages/datacommons-db/tests/
```

### Hermetic Integration Tests
The repository includes a hermetic testbed that uses Docker Compose to emulate Cloud Spanner, Cloud Storage, Ingestion Helper, and serving containers locally without incurring GCP cloud costs:

```bash
uv run pytest tests/integration/suites/ \
    --instance local \
    --test-config foobar_wages
```

> **Single Source of Truth**: For complete details on Docker Compose emulation, developer fast-iteration flags (such as `--reuse-data` to skip re-ingestion), and running tests against live GCP sandbox projects, refer to the [Integration Tests Guide](../tests/integration/README.md).

---

## Debugging Workflows and Common Gotchas

### Missing `DC_API_KEY`
* **Symptom**: Integration tests or local serving queries fail with unauthorized or upstream RPC errors.
* **Resolution**: DCP federates queries against base Google Data Commons. Obtain a key from [apikeys.datacommons.org](https://apikeys.datacommons.org) and ensure `DC_API_KEY` is exported in your shell:
  ```bash
  export DC_API_KEY="your-api-key"
  ```

### BigQuery Reservation Collision
* **Symptom**: `terraform apply` fails with an error indicating that a BigQuery slot reservation already exists in the project and region.
* **Resolution**: Google Cloud allows only one BigQuery slot reservation per project per region. When sharing a development project (such as `datcom-website-dev`), set `spanner_create_bigquery_reservation = false` in your `terraform.tfvars`.

### Spanner Emulator Port Conflicts
* **Symptom**: Hermetic integration tests report `Address already in use` on port 9010 or 9020.
* **Resolution**: Ensure no previous Docker Compose test containers are running:
  ```bash
  docker compose -f tests/integration/emulated/docker-compose.yml down -v
  ```

### Service Account Token Creator Missing
* **Symptom**: `datacommons admin init-db` or `datacommons admin ingest start` fails with HTTP 403 / IAM permission denied when acquiring credentials.
* **Resolution**: Ensure your GCP user account has `roles/iam.serviceAccountTokenCreator` on the workflow service account:
  ```bash
  gcloud iam service-accounts add-iam-policy-binding <workflow-sa-email> \
      --member="user:$(gcloud config get-value account)" \
      --role="roles/iam.serviceAccountTokenCreator" \
      --project=<project-id>
  ```


