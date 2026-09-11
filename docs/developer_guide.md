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
2. **Critical Scaffolding Contract**: Never alter or reformat line 166 in `infra/dcp/main.tf`:
   ```hcl
   module "stack" {
     source = "./modules/stack"
   ```
   The `datacommons admin init` CLI command uses regular expression matching on `source = "./modules/stack"` to rewrite the module source to the remote GitHub release URL for downstream users. Modifying this line breaks CLI scaffolding.
3. **Local Validation and Testing**: Validate and test Terraform changes by copying `infra/dcp/terraform.tfvars.template` to `infra/dcp/terraform.tfvars` and running:
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
