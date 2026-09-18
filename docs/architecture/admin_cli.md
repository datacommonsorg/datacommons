# Data Commons Admin CLI Architecture and Terraform Integration

## Overview

The Data Commons Platform (DCP) provides the `datacommons admin` CLI tool to automate deployment scaffolding, database initialization, schema migrations, and batch ingestion execution.

The CLI acts as an operational bridge between human operators, declarative Terraform state, and Google Cloud APIs.

This document details the CLI packaging architecture, the Terraform scaffolding pipeline, state inspection modes (local state vs remote Cloud Storage state), and administrative operational execution flows.

---

## Package Structure and Command Taxonomy

The CLI tooling is structured across two packages in the repository:
* **[packages/datacommons-cli/](../../packages/datacommons-cli)**: Thin distribution package exposing the `datacommons` console script entrypoint.
* **[packages/datacommons-admin/](../../packages/datacommons-admin)**: Core administration package containing Click command groups and cloud integrations:
  * `init/`: Deployment scaffolding and template rewrite logic ([init_cli.py](../../packages/datacommons-admin/datacommons_admin/init/init_cli.py), [scaffold_utils.py](../../packages/datacommons-admin/datacommons_admin/init/utils/scaffold_utils.py)).
  * `db/`: Database initialization and schema migration runner ([db_cli.py](../../packages/datacommons-admin/datacommons_admin/db/db_cli.py), [migration_utils.py](../../packages/datacommons-admin/datacommons_admin/db/utils/migration_utils.py)).
  * `ingest/`: Workflows launch client and runtime configuration inspector ([ingest_cli.py](../../packages/datacommons-admin/datacommons_admin/ingest/ingest_cli.py), [ingestion_job_client.py](../../packages/datacommons-admin/datacommons_admin/core/clients/ingestion_job_client.py)).
  * `core/clients/`: Authenticated HTTP clients for the Ingestion Helper service ([ingestion_helper_client.py](../../packages/datacommons-admin/datacommons_admin/core/clients/ingestion_helper_client.py)) and Cloud Workflows / Cloud Run Jobs ([ingestion_job_client.py](../../packages/datacommons-admin/datacommons_admin/core/clients/ingestion_job_client.py)).
  * `core/terraform/`: Local and remote GCS Terraform state parser ([state.py](../../packages/datacommons-admin/datacommons_admin/core/terraform/state.py)) and strongly typed deployment output model ([models.py](../../packages/datacommons-admin/datacommons_admin/core/terraform/models.py)).
  * `core/utils/`: Shared interactive terminal prompt and formatting helpers ([ui_utils.py](../../packages/datacommons-admin/datacommons_admin/core/utils/ui_utils.py)).
  * `tests/`: Automated unit and contract test suite verifying state parsing, GCS URI resolution, HCL output parity, and command behaviors ([tests/](../../packages/datacommons-admin/tests)).

### CLI Command Taxonomy
* **`datacommons admin init`**: Scaffolds a new deployment directory by fetching Terraform templates, modifying module sources, and configuring instance variables.
* **`datacommons admin init-db`**: Initializes the Cloud Spanner database schema, runs pending migrations, and seeds required base metadata.
* **`datacommons admin migrate-db`**: Checks for and applies pending Spanner schema migrations with distributed locking.
* **`datacommons admin seed-db`**: Seeds base statistical variable metadata and graph definitions.
* **`datacommons admin ingest start`**: Launches a Cloud Workflows ingestion run for registered datasets.
* **`datacommons admin ingest show-config`**: Displays current runtime environment variables from the preprocessing job.

---

## Terraform Scaffolding Pipeline (`admin init`)

When an operator runs `datacommons admin init`, the CLI generates a ready-to-deploy workspace through a four-step lifecycle:
1. **Download Templates**: Fetches `main.tf`, `variables.tf`, `outputs.tf`, and `terraform.tfvars.template` from GitHub for the specified release tag.
2. **Apply Source Regex Substitution**: Rewrites the local relative module source (`./modules/stack`) to the remote Git reference (`git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref=<tag>`).
3. **Populate Template Tokens**: Replaces placeholder tokens (`$$PROJECT_ID$$`, `$$INSTANCE_NAME$$`, `$$DC_API_KEY$$`) with user-supplied values.
4. **Write Generated Workspace**: Emits `main.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars`, `README.md`, and optionally `backend.tf` into the destination directory.

### The Source Regex Substitution Contract
During scaffolding, `_setup_dcp_config_dir()` in [scaffold_utils.py](../../packages/datacommons-admin/datacommons_admin/init/utils/scaffold_utils.py) rewrites the stack module source from a local relative path into a remote Git release URL:
```
source = "./modules/stack"  ==>  source = "git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref=<tag>"
```

**Critical Contract Rule**: The `module "stack"` block in [infra/dcp/main.tf](../../infra/dcp/main.tf) must maintain `source = "./modules/stack"` on a single line. The substitution logic in [scaffold_utils.py](../../packages/datacommons-admin/datacommons_admin/init/utils/scaffold_utils.py) uses the regular expression `r'source\s*=\s*["\']\./modules/stack["\']'`. Modifying line breaks or the path structure within this string breaks the match, causing scaffolded user workspaces to retain the local relative path and fail during subsequent `terraform init` execution.

---

## State Inspection Modes: Local vs Remote GCS State

Administrative commands (`init-db`, `migrate-db`, `ingest start`, `ingest show-config`) require access to infrastructure attributes provisioned by Terraform, such as the Spanner database ID, Cloud Workflows name, and Cloud Run service URLs.

The CLI resolves these attributes dynamically via [state.py](../../packages/datacommons-admin/datacommons_admin/core/terraform/state.py) using two execution modes, parsing and validating outputs into the strongly typed `TerraformOutputs` dataclass defined in [models.py](../../packages/datacommons-admin/datacommons_admin/core/terraform/models.py):

* **Remote GCS State Mode**: Used when the operator passes `--tf-state-location` or passes `--project-id` and `--instance-name` together. Reads `default.tfstate` directly from Cloud Storage via the Google Cloud Client Library without requiring the local `terraform` CLI binary.
* **Local State Mode**: Used when invoked within an active deployment directory without remote state flags. Executes `terraform output -json` as a local subprocess and parses the JSON stdout.

### Local State Mode (Interactive Workstations)
When invoked inside an initialized deployment directory without remote state flags:
* `state.py` locates the local `terraform` binary using `shutil.which("terraform")`.
* It executes `terraform output -json` as a subprocess within the current working directory.
* It parses the standard output JSON into an in-memory dictionary of output values.

### Remote GCS State Mode (Headless CI/CD and Automation)
In automated environments (such as GitHub Actions, Cloud Build, or remote operational hosts), local `.tfstate` files or the `terraform` CLI binary might not be present.
* Operators pass state flags to the root `admin` group:
  ```bash
  datacommons admin \
      --project-id datcom-website-dev \
      --instance-name dev-alice \
      ingest start --imports ALL_IMPORTS
  ```
* When `--project-id` and `--instance-name` are passed, `state.py` downloads the state blob from canonical URI `gs://tf-state-<instance-name>-<project-id>/terraform/state/<instance-name>/default.tfstate`. If `--tf-state-location` is specified, it downloads directly from the provided GCS URI.
* The CLI extracts the `outputs` JSON block directly from the remote state document.

### Typed Terraform Output Contract (`TerraformOutputs`)
Rather than relying on loose dictionary lookups, CLI subcommands pass the root CLI state flags (`project_id`, `instance_name`, `tf_state_location`) into `get_terraform_outputs()` in [state.py](../../packages/datacommons-admin/datacommons_admin/core/terraform/state.py) to parse deployment state into the `TerraformOutputs` dataclass ([models.py](../../packages/datacommons-admin/datacommons_admin/core/terraform/models.py)):
* **Validation and Field Extraction**: `TerraformOutputs.from_state_outputs()` extracts scalar values from Terraform's `{"value": ...}` JSON envelope, strips whitespace, enforces that required attributes are non-empty, and computes derived paths such as `ingestion_temp_location` (`gs://<storage_artifacts_bucket_name>/temp`).
* **Precedence**: Passing explicit remote flags (`--project-id` and `--instance-name`, or `--tf-state-location`) strictly overrides local state detection, ensuring deterministic execution on CI/CD runners regardless of working directory.

### Test Suite Architecture
The state resolution and contract verification suite spans two complementary test modules under `packages/datacommons-admin/tests/core/`:
* **State Resolution Unit Tests ([test_tf_state.py](../../packages/datacommons-admin/tests/core/test_tf_state.py))**:
  * Mocks subprocess execution of `terraform output -json` for local state mode and Google Cloud Storage client downloads for remote state mode.
  * Verifies handling of missing state files (HTTP 404), permission errors (HTTP 403), malformed JSON, and missing required output keys.
* **Automated HCL Contract Tests ([test_tf_contract.py](../../packages/datacommons-admin/tests/core/test_tf_contract.py))**:
  * Dynamically parses [infra/dcp/outputs.tf](../../infra/dcp/outputs.tf) at test time and verifies that every field defined on `TerraformOutputs` is explicitly declared in `infra/dcp/outputs.tf`.

---

## Operational Execution Flows

### Database Initialization Flow (`datacommons admin init-db`)
1. **Output Discovery**: Calls `get_terraform_outputs()` in [state.py](../../packages/datacommons-admin/datacommons_admin/core/terraform/state.py) to load validated project, Spanner, and Ingestion Helper endpoints from Terraform state.
2. **Client Authentication**: Instantiates `IngestionHelperClient` configured with OpenID Connect (OIDC) ID token impersonation for the workflow service account. Prerequisite: the executing user account must hold `roles/iam.serviceAccountTokenCreator` on the workflow service account.
3. **Database Check and Safety Guard**: Calls `is_database_initialized(project_id, instance_id, database_id)`. If the `Node` table exists, the CLI halts execution to avoid overwriting existing data, directing operators to run `migrate-db` or `seed-db` instead.
4. **Base Schema Creation**: Sends an authenticated HTTP POST request to `${ingestion_service_url}/database/initialize` to apply base DDL scripts via the Ingestion Helper service in `datcom-import`. This creates the required Spanner tables (`Node`, `Edge`, `TimeSeries`, `Observation`, `ImportStatus`, `IngestionHistory`, `ImportVersionHistory`, `IngestionLock`, `KeyValueStore`, `NodeEmbedding`), secondary indexes, and embedding models.
5. **Schema Migrations (Local Execution)**: Runs `_run_migrations()`, executing pending Python migration scripts subclassing `SchemaMigration` from [packages/datacommons-db/datacommons_db/migrations/migration_scripts/](../../packages/datacommons-db/datacommons_db/migrations/migration_scripts). While base DDL runs remotely through Ingestion Helper, schema migrations execute locally within the CLI Python process via `datacommons_db.migrations.MigrationRunner`, establishing a direct connection to Cloud Spanner. The runner coordinates distributed lock state by acquiring and releasing `workflow_id="schema-migration"` in the `IngestionLock` table via the Ingestion Helper lock endpoints (`/database/lock/acquire` and `/database/lock/release`).
6. **Metadata Seeding**: Unless `--init-only` is passed, calls `${ingestion_service_url}/database/seed` to populate fundamental statistical entities and units.

### Schema Migration Flow (`datacommons admin migrate-db`)
1. **Output Discovery**: Resolves Spanner instance, database, project ID, and Ingestion Helper configuration from Terraform state.
2. **Pending Migration Check**: Queries pending migrations via `MigrationRunner.get_pending_migrations()`. If no migrations are pending, the command exits.
3. **Operator Confirmation**: If pending migrations exist, prompts for confirmation before applying DDL modifications, unless auto-approved via `-y` or `--yes`.
4. **Lock Coordination & Application**: Acquires the distributed lock via Ingestion Helper (`workflow_id="schema-migration"`), applies all pending migrations directly to Cloud Spanner, and releases the lock in a finally block.

### Ingestion Trigger Flow (`datacommons admin ingest start`)
1. **Output Discovery**: Calls `get_terraform_outputs()` to resolve the Cloud Workflow name, service account email, project ID, region, Spanner identifiers, and derived temporary GCS location (`gs://<storage_artifacts_bucket_name>/temp`) directly from Terraform state without requiring extra runtime Cloud Run API calls.
2. **Workflow Execution**:
   * Parses the comma-separated `--imports` flag into a list of import names.
   * Constructs the execution argument JSON payload containing `tempLocation`, `spannerInstanceId`, `spannerDatabaseId`, `region`, and `imports`.
   * Sends an authenticated HTTP POST request to the Google Cloud Workflow Executions REST API (`https://workflowexecutions.googleapis.com/v1/{full_workflow_name}/executions`) using an `AuthorizedSession` authenticated via impersonated service account credentials.
3. **Console Link Generation**: Formulates and prints a direct Google Cloud Console URL:
   ```
   https://console.cloud.google.com/workflows/workflow/<region>/<workflow_name>/execution/<execution_id>/summary?project=<project_id>
   ```
   This allows operators to immediately monitor live execution progress.
4. **Asynchronous Pipeline Coordination**: The Cloud Workflow coordinates pipeline execution across preprocessing, Dataflow, postprocessing, and cache invalidation. During execution, the workflow manages the `IngestionLock`, `IngestionHistory`, and `ImportStatus` tables by calling Ingestion Helper endpoints; the Admin CLI process exits immediately after triggering the execution.

### Runtime Configuration Flow (`datacommons admin ingest show-config`)
1. **Output Discovery**: Calls `get_terraform_outputs()` to read and display core deployment attributes (`project_id`, `region`, `ingestion_workflow_service_account_email`, and optional `ingestion_prep_job_name`) directly from Terraform state.
2. **Job Environment Inspection**: If `ingestion_prep_job_name` is configured in the deployment, queries the Cloud Run Admin API for the preprocessing job definition and prints its container environment variables, distinguishing explicit values from secret references.

---

## Related Documentation

* **Platform Architecture**: Consult [Platform Architecture](platform_architecture.md) for end-to-end serving and ingestion pipeline mechanics.
* **Terraform Stack Architecture**: Consult [Terraform Stack Architecture](terraform_stack.md) for module orchestration, IAM policies, and infrastructure guardrails.
* **Developer Guide**: Consult [Developer Guide](../developer_guide.md#working-on-the-cli-datacommons-cli-and-datacommons-admin) for instructions on running and testing unreleased CLI packages locally.
