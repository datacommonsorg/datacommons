# Data Commons Admin CLI Architecture and Terraform Integration

## Overview

The Data Commons Platform (DCP) provides the `datacommons admin` CLI tool to automate deployment scaffolding, database initialization, schema migrations, and batch ingestion execution.

The CLI acts as an operational bridge between human operators, declarative Terraform state, and Google Cloud APIs.

This document details the CLI packaging architecture, the Terraform scaffolding pipeline, state inspection modes (local state vs remote Cloud Storage state), and the choreography of administrative operations.

---

## 1. Package Structure and Command Taxonomy

The CLI tooling is organized into two Python packages under `packages/` in the `datacommonsorg/datacommons` repository:

```
packages/
├── datacommons-cli/                  # Distribution package
│   ├── pyproject.toml                # Declares console script: datacommons
│   └── datacommons_cli/
│       └── cli.py                    # Entrypoint router delegating to admin
│
└── datacommons-admin/                # Core business logic package
    ├── pyproject.toml                # Dependencies: google-cloud-storage, click, etc.
    ├── datacommons_admin/
    │   ├── admin_cli.py              # Root click group: datacommons admin
    │   ├── init/                     # Scaffolding logic (admin init)
    │   │   ├── init_cli.py
    │   │   └── utils/scaffold_utils.py
    │   ├── db/                       # Database lifecycle (init-db, migrate-db, seed-db)
    │   │   ├── db_cli.py
    │   │   └── utils/migration_utils.py
    │   ├── ingest/                   # Ingestion operations (ingest start, show-config)
    │   │   └── ingest_cli.py
    │   └── core/                     # Shared utilities and API clients
    │       ├── clients/              # IngestionHelperClient, IngestionJobClient
    │       └── utils/tf_utils.py     # Terraform state parser and output extractor
    └── tests/
        └── core/test_tf_contract.py  # Strict contract tests between CLI and Terraform
```

### CLI Command Taxonomy
* **`datacommons admin init`**: Scaffolds a new deployment directory by fetching Terraform templates, modifying module sources, and configuring instance variables.
* **`datacommons admin init-db`**: Initializes the Cloud Spanner database schema, runs pending migrations, and seeds required base metadata.
* **`datacommons admin migrate-db`**: Checks for and applies pending Spanner schema migrations.
* **`datacommons admin seed-db`**: Seeds base statistical variable metadata and graph definitions.
* **`datacommons admin ingest start`**: Launches a Cloud Workflows ingestion run for registered datasets.
* **`datacommons admin ingest show-config`**: Displays current runtime environment variables from the preprocessing job.

---

## 2. Terraform Scaffolding Pipeline (`admin init`)

When an operator runs `datacommons admin init`, the CLI generates a ready-to-deploy workspace without requiring a local git clone of the platform repository.

```
                          GitHub Repository
                 (datacommonsorg/datacommons @ ref)
                                  │
                                  │ HTTP GET raw templates
                                  ▼
┌───────────────────────────────────────────────────────────────────────┐
│ datacommons admin init                                                │
│                                                                       │
│ 1. Download templates:                                                │
│    - variables.tf                                                     │
│    - main.tf                                                          │
│    - outputs.tf                                                       │
│    - terraform.tfvars.template                                        │
│                                                                       │
│ 2. Apply Source Regex Substitution Contract:                          │
│    Rewrite: source = "./modules/stack"                                │
│    To:      source = "git::https://...//infra/dcp/modules/stack?ref=" │
│                                                                       │
│ 3. Populate template tokens:                                          │
│    $$PROJECT_ID$$    -> user project ID                               │
│    $$INSTANCE_NAME$$ -> user namespace                                │
│    $$DC_API_KEY$$    -> user API key                                  │
│                                                                       │
│ 4. Write generated workspace:                                         │
│    ./<namespace>/main.tf                                              │
│    ./<namespace>/variables.tf                                         │
│    ./<namespace>/outputs.tf                                           │
│    ./<namespace>/terraform.tfvars                                     │
│    ./<namespace>/backend.tf (if remote state enabled)                 │
└───────────────────────────────────────────────────────────────────────┘
```

### The Source Regex Substitution Contract
The file `packages/datacommons-admin/datacommons_admin/init/utils/scaffold_utils.py` uses regular expression matching to convert local module paths into remote Git references:

```python
resolved_source = f"git::{GITHUB_REPO_URL}//infra/dcp/modules/stack?ref={ref}"
main_content = re.sub(
    r'source\s*=\s*["\']\./modules/stack["\']',
    f'source = "{resolved_source}"',
    main_content,
)
```

**Critical Contract Rule**: Line 166 in `infra/dcp/main.tf` must maintain the exact formatting:
```hcl
module "stack" {
  source = "./modules/stack"
```
If this line is modified (such as changing whitespace, breaking lines, or referencing a different relative directory), the regex fails to match. The resulting `main.tf` written to the user's workspace will retain the local relative path `./modules/stack`, causing subsequent `terraform init` commands to fail because the `./modules` directory does not exist in the scaffolded folder.

---

## 3. State Inspection Modes: Local vs Remote GCS State

Administrative commands (`init-db`, `migrate-db`, `ingest start`) require access to infrastructure attributes provisioned by Terraform, such as the Spanner database ID, Cloud Workflows name, and Cloud Run service URLs.

The CLI resolves these attributes dynamically via `datacommons_admin/core/utils/tf_utils.py` using two execution modes.

```
                  datacommons admin <subcommand>
                                │
                                ▼
               Does Click Context specify Remote Flags?
              (--project-id, --instance-name, or --tf-state-location)
                                │
               ┌────────────────┴────────────────┐
               │ YES                             │ NO
               ▼                                 ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│ Remote GCS State Mode        │  │ Local State Mode                 │
│ - Reads GCS state directly   │  │ - Spawns subprocess:             │
│   via Cloud Storage API      │  │   terraform output -json         │
│ - Requires zero local TF CLI │  │ - Parses stdout in current working│
│ - Ideal for CI/CD runners    │  │   directory                      │
└──────────────┬───────────────┘  └──────────────────┬───────────────┘
               │                                     │
               └──────────────────┬──────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│ Strongly Typed TerraformOutputs Dataclass                           │
│ (project_id, spanner_instance_id, ingestion_workflow_name, etc.)   │
└────────────────────────────────────────────────────────────────────┘
```

### 1. Local State Mode (Interactive Workstations)
When invoked inside an initialized deployment directory without remote state flags:
* `tf_utils.py` locates the local `terraform` binary using `shutil.which("terraform")`.
* It executes `terraform output -json` as a subprocess within the current working directory.
* It parses the standard output JSON into a dictionary of output values.

### 2. Remote GCS State Mode (Headless CI/CD and Automation)
In automated environments (such as GitHub Actions, Cloud Build, or remote operational hosts), local `.tfstate` files or the `terraform` CLI binary might not be present.
* Operators pass state flags to the root `admin` group:
  ```bash
  datacommons admin \
      --project-id datcom-website-dev \
      --instance-name dev-alice \
      ingest start --imports ALL_IMPORTS
  ```
* `tf_utils.py` uses the Google Cloud Storage Python client (`google-cloud-storage`) to download the `default.tfstate` blob directly from `gs://<instance-name>-dc-tfstate-<project-id>/default.tfstate`.
* The CLI extracts the `outputs` JSON block directly from the remote state document.

### Contract Enforcement (`test_tf_contract.py`)
To prevent drift between Terraform exports and CLI expectations, the test suite in `packages/datacommons-admin/tests/core/test_tf_contract.py` enforces three automated checks during CI:
1. Every field in the `TerraformOutputs` Python dataclass must exist in `infra/dcp/outputs.tf`.
2. Every `TF_OUTPUT_*` string constant in `tf_utils.py` must match a declared output in `infra/dcp/outputs.tf`.
3. Every output delegated by `infra/dcp/outputs.tf` to `module.stack` must be declared in `infra/dcp/modules/stack/outputs.tf`.

---

## 4. Administrative Operation Choreography

### 1. Database Initialization Flow (`datacommons admin init-db`)
1. **Output Discovery**: Reads `ingestion_service_url`, `ingestion_workflow_service_account_email`, `spanner_instance_id`, `spanner_database_id`, and `project_id` from Terraform state.
2. **Client Authentication**: Instantiates `IngestionHelperClient` configured with OpenID Connect (OIDC) impersonation tokens for the workflow service account.
3. **Database Check**: Calls `is_database_initialized(project_id, instance_id, database_id)`. If tables exist, skips DDL execution.
4. **Schema Creation**: Sends an authenticated HTTP request to `${ingestion_helper_url}/database/init` to apply base DDL scripts.
5. **Schema Migrations**: Runs `_run_migrations()`, executing pending SQL scripts in `packages/datacommons-db/migration_scripts/`.
6. **Metadata Seeding**: Calls `${ingestion_helper_url}/database/seed` to populate fundamental statistical entities and units.

### 2. Ingestion Trigger Flow (`datacommons admin ingest start`)
1. **Output Discovery**: Reads `ingestion_workflow_name`, `ingestion_workflow_service_account_email`, `ingestion_temp_location`, `project_id`, and `region`.
2. **Client Initialization**: Instantiates `IngestionJobClient` targeting the Google Cloud Workflows API.
3. **Workflow Execution**:
   * Prepares execution arguments containing the target dataset import names (`--imports <dataset>`), Cloud Spanner instance and database IDs, and temporary GCS locations.
   * Calls `googleapis.workflows.executions.create` using the Cloud Workflows service account identity.
4. **Console Link Generation**: Formulates and prints a direct Google Cloud Console URL:
   ```
   https://console.cloud.google.com/workflows/workflow/<region>/<workflow_name>/execution/<execution_id>/summary?project=<project_id>
   ```
   This allows operators to immediately monitor live execution progress across preprocessing, Dataflow, postprocessing, and cache invalidation.
