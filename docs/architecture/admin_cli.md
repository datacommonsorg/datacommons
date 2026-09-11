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
  * `db/`: Database initialization and schema migration runner ([db_cli.py](../../packages/datacommons-admin/datacommons_admin/db/db_cli.py)).
  * `ingest/`: Workflows launch client and runtime configuration inspector ([ingest_cli.py](../../packages/datacommons-admin/datacommons_admin/ingest/ingest_cli.py)).
  * `core/utils/tf_utils.py`: Local and remote GCS Terraform state parser ([tf_utils.py](../../packages/datacommons-admin/datacommons_admin/core/utils/tf_utils.py)).
  * `tests/`: Automated unit and contract parity test suite ([tests/](../../packages/datacommons-admin/tests)).

### CLI Command Taxonomy
* **`datacommons admin init`**: Scaffolds a new deployment directory by fetching Terraform templates, modifying module sources, and configuring instance variables.
* **`datacommons admin init-db`**: Initializes the Cloud Spanner database schema, runs pending migrations, and seeds required base metadata.
* **`datacommons admin migrate-db`**: Checks for and applies pending Spanner schema migrations.
* **`datacommons admin seed-db`**: Seeds base statistical variable metadata and graph definitions.
* **`datacommons admin ingest start`**: Launches a Cloud Workflows ingestion run for registered datasets.
* **`datacommons admin ingest show-config`**: Displays current runtime environment variables from the preprocessing job.

---

## Terraform Scaffolding Pipeline (`admin init`)

When an operator runs `datacommons admin init`, the CLI generates a ready-to-deploy workspace through a four-step lifecycle:
1. **Download Templates**: Fetches `main.tf`, `variables.tf`, `outputs.tf`, and `terraform.tfvars.template` from GitHub for the specified release tag.
2. **Apply Source Regex Substitution**: Rewrites the local relative module source (`./modules/stack`) to the remote Git reference (`git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref=<tag>`).
3. **Populate Template Tokens**: Replaces placeholder tokens (`$$PROJECT_ID$$`, `$$INSTANCE_NAME$$`, `$$DC_API_KEY$$`) with user-supplied values.
4. **Write Generated Workspace**: Emits `main.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars`, and optionally `backend.tf` into the destination directory.

### The Source Regex Substitution Contract
During scaffolding, `_setup_dcp_config_dir()` in [scaffold_utils.py](../../packages/datacommons-admin/datacommons_admin/init/utils/scaffold_utils.py) rewrites the stack module source from a local relative path into a remote Git release URL:
```
source = "./modules/stack"  ==>  source = "git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref=<tag>"
```

**Critical Contract Rule**: The `module "stack"` block in [infra/dcp/main.tf](../../infra/dcp/main.tf) must maintain `source = "./modules/stack"` on a single line. Modifying line breaks or whitespace within this string breaks the regular expression match, causing scaffolded user workspaces to retain the local relative path and fail during subsequent `terraform init` execution.

---

## State Inspection Modes: Local vs Remote GCS State

Administrative commands (`init-db`, `migrate-db`, `ingest start`) require access to infrastructure attributes provisioned by Terraform, such as the Spanner database ID, Cloud Workflows name, and Cloud Run service URLs.

The CLI resolves these attributes dynamically via [tf_utils.py](../../packages/datacommons-admin/datacommons_admin/core/utils/tf_utils.py) using two execution modes, parsing outputs into an in-memory dictionary and accessing values through dedicated helper functions:

* **Remote GCS State Mode**: Used when the operator passes `--tf-state-location` or passes `--project-id` and `--instance-name` together. Reads `default.tfstate` directly from Cloud Storage via the Google Cloud Client Library without requiring the local `terraform` CLI binary.
* **Local State Mode**: Used when invoked within an active deployment directory without remote state flags. Executes `terraform output -json` as a local subprocess and parses the JSON stdout.

### Local State Mode (Interactive Workstations)
When invoked inside an initialized deployment directory without remote state flags:
* `tf_utils.py` locates the local `terraform` binary using `shutil.which("terraform")`.
* It executes `terraform output -json` as a subprocess within the current working directory.
* It parses the standard output JSON into a dictionary of output values.

### Remote GCS State Mode (Headless CI/CD and Automation)
In automated environments (such as GitHub Actions, Cloud Build, or remote operational hosts), local `.tfstate` files or the `terraform` CLI binary might not be present.
* Operators pass state flags to the root `admin` group:
  ```bash
  datacommons admin \
      --project-id datcom-website-dev \
      --instance-name dev-alice \
      ingest start --imports ALL_IMPORTS
  ```
* When `--project-id` and `--instance-name` are passed, `tf_utils.py` downloads the state blob from canonical URI `gs://tf-state-<instance-name>-<project-id>/terraform/state/<instance-name>/default.tfstate`. If `--tf-state-location` is specified, it downloads directly from the provided GCS URI.
* The CLI extracts the `outputs` JSON block directly from the remote state document.

### Terraform Output Key Mapping
`tf_utils.py` defines explicit string constants for required outputs:
* Database initialization: `spanner_instance_id`, `spanner_database_id`, `ingestion_service_url`, `ingestion_workflow_service_account_email`, `project_id`.
* Data ingestion: `ingestion_prep_job_name`, `ingestion_workflow_service_account_email`, `project_id`, `region`, `ingestion_workflow_name`.

Dedicated helper functions (`get_spanner_instance_id()`, `get_ingestion_prep_job_name()`, etc.) retrieve each output on-demand through `get_terraform_output(key)`. The function caches output dictionaries across repeated lookups within a command lifecycle and validates that returned values are non-empty.

Passing explicit remote flags strictly overrides local state detection, ensuring deterministic execution on CI/CD runners regardless of working directory.

---

## Operational Execution Flows

### Database Initialization Flow (`datacommons admin init-db`)
1. **Output Discovery**: Reads `ingestion_service_url`, `ingestion_workflow_service_account_email`, `spanner_instance_id`, `spanner_database_id`, and `project_id` from Terraform state.
2. **Client Authentication**: Instantiates `IngestionHelperClient` configured with OpenID Connect (OIDC) impersonation tokens for the workflow service account. (*Prerequisite: the executing user account must hold `roles/iam.serviceAccountTokenCreator` on the workflow service account.*)
3. **Database Check and Safety Guard**: Calls `is_database_initialized(project_id, instance_id, database_id)`. If the `Node` table exists, the CLI safely halts execution to avoid overwriting live databases, directing operators to run `migrate-db` or `seed-db` instead.
4. **Base Schema Creation**: Sends an authenticated HTTP POST request to `${ingestion_helper_url}/database/initialize` to apply base DDL scripts via the Ingestion Helper.
5. **Schema Migrations (Local Execution)**: Runs `_run_migrations()`, executing pending Python migration scripts subclassing `SchemaMigration` from [packages/datacommons-db/datacommons_db/migrations/migration_scripts/](../../packages/datacommons-db/datacommons_db/migrations/migration_scripts). While base DDL runs remotely through Ingestion Helper, schema migrations execute locally within the CLI Python process via `datacommons_db.migrations.MigrationRunner`, establishing a direct connection to Cloud Spanner and coordinating migration lock state (`workflow_id="schema-migration"`).
6. **Metadata Seeding**: Calls `${ingestion_helper_url}/database/seed` to populate fundamental statistical entities and units.

### Ingestion Trigger Flow (`datacommons admin ingest start`)
1. **Output Discovery**: Reads `ingestion_workflow_name`, `ingestion_prep_job_name`, `ingestion_workflow_service_account_email`, `project_id`, and `region` from Terraform state.
2. **Client Initialization and Environment Discovery**: Instantiates `IngestionJobClient` targeting the Google Cloud Workflows API. Inspects the preprocessing Cloud Run job environment configuration to retrieve runtime parameters, including `TEMP_LOCATION`, `GCP_SPANNER_INSTANCE_ID`, and `GCP_SPANNER_DATABASE_NAME`.
3. **Workflow Execution**:
   * Prepares execution arguments containing the target dataset import names (`--imports <dataset>`), Cloud Spanner instance and database IDs, and the temporary GCS location (`tempLocation`).
   * Calls `googleapis.workflows.executions.create` using the Cloud Workflows service account identity.
4. **Console Link Generation**: Formulates and prints a direct Google Cloud Console URL:
   ```
   https://console.cloud.google.com/workflows/workflow/<region>/<workflow_name>/execution/<execution_id>/summary?project=<project_id>
   ```
   This allows operators to immediately monitor live execution progress across preprocessing, Dataflow, postprocessing, and cache invalidation.

---

## Related Documentation

* **Platform Architecture**: Consult [Platform Architecture](platform_architecture.md) for end-to-end serving and ingestion pipeline mechanics.
* **Terraform Stack Architecture**: Consult [Terraform Stack Architecture](terraform_stack.md) for module orchestration, IAM policies, and infrastructure guardrails.
* **Developer Guide**: Consult [Developer Guide](../developer_guide.md#working-on-the-cli-datacommons-cli-and-datacommons-admin) for instructions on running and testing unreleased CLI packages locally.
