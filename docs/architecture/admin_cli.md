# Data Commons Admin CLI Architecture and Terraform Integration

## Overview

The Data Commons Platform (DCP) provides the `datacommons admin` CLI tool to automate deployment scaffolding, database initialization, schema migrations, and batch ingestion execution.

The CLI acts as an operational bridge between human operators, declarative Terraform state, and Google Cloud APIs.

This document details the CLI packaging architecture, the Terraform scaffolding pipeline, state inspection modes (local state vs remote Cloud Storage state), and administrative operational execution flows.

---

## 1. Package Structure and Command Taxonomy

The CLI tooling is structured across two packages in the repository:
* **[packages/datacommons-cli/](../../packages/datacommons-cli)**: Thin distribution package exposing the `datacommons` console script entrypoint.
* **[packages/datacommons-admin/](../../packages/datacommons-admin)**: Core administration package containing Click command groups and cloud integrations:
  * `init/`: Deployment scaffolding and template rewrite logic ([init_cli.py](../../packages/datacommons-admin/datacommons_admin/init/init_cli.py), [scaffold_utils.py](../../packages/datacommons-admin/datacommons_admin/init/utils/scaffold_utils.py)).
  * `db/`: Database initialization and schema migration runner ([db_cli.py](../../packages/datacommons-admin/datacommons_admin/db/db_cli.py)).
  * `ingest/`: Workflows launch client and runtime configuration inspector ([ingest_cli.py](../../packages/datacommons-admin/datacommons_admin/ingest/ingest_cli.py)).
  * `core/utils/tf_utils.py`: Local and remote GCS Terraform state parser ([tf_utils.py](../../packages/datacommons-admin/datacommons_admin/core/utils/tf_utils.py)).
  * `tests/core/test_tf_contract.py`: Automated contract parity tests ([test_tf_contract.py](../../packages/datacommons-admin/tests/core/test_tf_contract.py)).

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
During scaffolding, `_setup_dcp_config_dir()` in [scaffold_utils.py](../../packages/datacommons-admin/datacommons_admin/init/utils/scaffold_utils.py#L176-L182) rewrites the stack module source from a local relative path into a remote Git release URL:
```
source = "./modules/stack"  ==>  source = "git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref=<tag>"
```

**Critical Contract Rule**: The `module "stack"` block in [infra/dcp/main.tf](../../infra/dcp/main.tf) must maintain `source = "./modules/stack"` on a single line. Modifying line breaks or whitespace within this string breaks the regular expression match, causing scaffolded user workspaces to retain the local relative path and fail during subsequent `terraform init` execution.

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
To prevent drift between Terraform exports and CLI expectations, the test suite in [test_tf_contract.py](../../packages/datacommons-admin/tests/core/test_tf_contract.py) enforces four automated contract checks during CI:
1. Every field in the `TerraformOutputs` Python dataclass must exist in [infra/dcp/outputs.tf](../../infra/dcp/outputs.tf).
2. Every `TF_OUTPUT_*` string constant in `tf_utils.py` must match a declared output in [infra/dcp/outputs.tf](../../infra/dcp/outputs.tf).
3. Every output delegated by `infra/dcp/outputs.tf` to `module.stack` must be declared in [infra/dcp/modules/stack/outputs.tf](../../infra/dcp/modules/stack/outputs.tf).
4. Unit test mock fixtures in `conftest.py` must maintain field parity with `TerraformOutputs` (`test_conftest_fixtures_in_sync_with_contract`).

Passing explicit remote flags (`--project-id`, `--instance-name`, `--tf-state-location`) strictly overrides local state detection, ensuring deterministic execution on CI/CD runners regardless of working directory.

---

## 4. Operational Execution Flows

### 1. Database Initialization Flow (`datacommons admin init-db`)
1. **Output Discovery**: Reads `ingestion_service_url`, `ingestion_workflow_service_account_email`, `spanner_instance_id`, `spanner_database_id`, and `project_id` from Terraform state.
2. **Client Authentication**: Instantiates `IngestionHelperClient` configured with OpenID Connect (OIDC) impersonation tokens for the workflow service account. (*Prerequisite: the executing user account must hold `roles/iam.serviceAccountTokenCreator` on the workflow service account.*)
3. **Database Check**: Calls `is_database_initialized(project_id, instance_id, database_id)`. If tables exist, skips DDL execution.
4. **Schema Creation**: Sends an authenticated HTTP request to `${ingestion_helper_url}/database/init` to apply base DDL scripts.
5. **Schema Migrations**: Runs `_run_migrations()`, executing pending Python migration scripts subclassing `SchemaMigration` from [packages/datacommons-db/datacommons_db/migrations/migration_scripts/](../../packages/datacommons-db/datacommons_db/migrations/migration_scripts).
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
