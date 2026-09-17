# Data Commons CLI

<p align="center">
  <a href="https://www.datacommons.org"><img src="https://datacommons.org/images/dc-logo.svg" alt="Data Commons" width="120"></a>
</p>

<p align="center">
  <em>Standard command-line interface for interacting with, deploying, and administering the Data Commons Platform.</em>
</p>

---

[Data Commons](https://www.datacommons.org) is an open-source project initiated by Google that aggregates data from hundreds of public sources, such as the US Census, Eurostat, CDC, and UN, into a unified, standard Knowledge Graph.

The **Data Commons Platform** provides the infrastructure to run your own private instance of Data Commons, allowing you to seamlessly combine public datasets with your own custom, private data using modern APIs, graph query engines, and visualization dashboards.

---

## Installation

Install the Data Commons CLI using `pip` or `uv`:

### Install with `pip`

```bash
pip install --user datacommons-cli
```

If the datacommons command is not found after installing, add Python's user-binary directory to your PATH:

```
export PATH="$PATH:$(python3 -m site --user-base)/bin"
```

### Install with `uv`

```bash
uv tool install datacommons-cli
```

If the `datacommons` command is not found after installing, add the appropriate directory to your PATH:

```
export PATH="~/.local/bin:$PATH"
```

### With `uvx`

Or execute `datacommons-cli` on-the-fly without installation using `uvx`:

```bash
uvx datacommons-cli --help
```

## Help & Documentation

For full documentation, tutorials, and deployment guides, visit:
👉 **[docs.datacommons.org](https://docs.datacommons.org)**

---

## Usage

The CLI exposes standard operations under the main `datacommons` entrypoint. You can check the version and get help instantly:

```bash
# Show help menu
datacommons --help

# Show version
datacommons --version
```

---

## Administrative Commands

All infrastructure setup, database operations, and ingestion pipelines are managed under the `admin` sub-command group:

```bash
datacommons admin [OPTIONS] COMMAND [ARGS]...
```

### Execution Modes: Local vs. Remote State

The `admin` commands interact with your deployed GCP resources (Cloud Spanner, Ingestion Helper Cloud Run service, and Cloud Workflows). To resolve deployment outputs (such as service URLs and Spanner IDs), the CLI supports two execution modes:

#### 1. Local State Mode (Default)
When executed from inside your initialized Terraform deployment directory (e.g., `cd my-instance`), the CLI automatically inspects local Terraform state outputs using `terraform output -json`:

```bash
cd my-instance
datacommons admin init-db
```

#### 2. Remote GCS State Mode (Stateless / CI/CD)
When running from outside the deployment directory, on a remote workstation, or within automated CI/CD pipelines (e.g., Cloud Build, GitHub Actions), you do not need local Terraform files, `.tfstate` files, or the `terraform` CLI installed. 

Pass remote-state options directly to the `admin` command group:

```bash
# Locate remote state automatically via project ID and instance name:
datacommons admin --project-id my-project --instance-name my-instance init-db

# Or specify the exact GCS state URI:
datacommons admin --tf-state-location gs://my-tfstate-bucket/terraform/state/my-instance/default.tfstate migrate-db -y
```

> [!TIP]
> **Why use Remote GCS State Mode?**
> - **Zero Local Files**: Reads Terraform state outputs directly from Google Cloud Storage into memory using the Cloud Storage API.
> - **Secure & Stateless**: Adheres to infrastructure security best practices by avoiding downloading `.tfstate` files to local disks or exposing local Terraform execution.
> - **CI/CD Ready**: Allows automated jobs to trigger migrations or ingestion without cloning or initializing the Terraform repository.

#### Remote-State Global Options

These options can be passed to `datacommons admin` for any administrative command:

| Option | Description |
| --- | --- |
| `--project-id TEXT` | GCP project ID used to locate the canonical remote Terraform state bucket (`gs://<project_id>-<instance_name>-tfstate`). Must be specified together with `--instance-name`. |
| `--instance-name TEXT` | DCP instance name (prefix) used to locate the remote Terraform state bucket. Must be specified together with `--project-id`. |
| `--tf-state-location TEXT` | Exact GCS URI of the Terraform state file (e.g. `gs://bucket/prefix/default.tfstate`). Overrides canonical bucket derivation. |

---

### Available Commands

| Command | Description |
| --- | --- |
| **`init`** | Scaffolds a localized Terraform deployment directory for the Data Commons Platform on Google Cloud Platform (GCP). |
| **`init-db`** | Configures database schemas and seeds baseline tables on Cloud Spanner via the Ingestion Helper service. |
| **`migrate-db`** | Checks and applies pending schema migrations to the Cloud Spanner database. |
| **`seed-db`** | Seeds or re-applies base geographic entities and schema definitions to Cloud Spanner. |
| **`ingest start`** | Triggers a Cloud Workflows + Cloud Run background data ingestion pipeline for custom datasets. |
| **`ingest show-config`**| Displays current background ingestion parameters, service URLs, and Cloud Run job environment variables. |

---

### Command Reference & Examples

#### `datacommons admin init`
Scaffolds a new deployment directory containing `main.tf`, `terraform.tfvars`, and a deployment README.

```bash
datacommons admin init --project-id my-gcp-project --instance-name my-instance
```

Key Options:
- `--project-id TEXT`: GCP project ID for platform resources.
- `--instance-name TEXT`: Instance name prefix for provisioned resources (also accepts `--namespace` for backward compatibility).
- `--dc-api-key TEXT`: Data Commons API key.
- `--tf-remote-state / --no-tf-remote-state`: Enable/disable remote state management in GCS (default: enabled).
- `--tf-state-bucket TEXT`: Custom GCS bucket name for Terraform state (defaults to `<project_id>-<instance_name>-tfstate`).
- `--force`: Overwrite existing files in the target directory if present.

#### `datacommons admin init-db`
Initializes database schema, applies all migrations, and seeds baseline geographic data on Cloud Spanner. If the database has already been initialized, the command safely detects it and prompts you to use `migrate-db` or `seed-db`.

```bash
# Local state mode:
datacommons admin init-db

# Remote state mode:
datacommons admin --project-id my-project --instance-name my-instance init-db

# Initialize schemas and migrations only (skip baseline data seeding):
datacommons admin init-db --init-only
```

#### `datacommons admin migrate-db`
Inspects pending Spanner schema migrations and applies them sequentially using distributed locks.

```bash
# Interactive mode (prompts before applying pending migrations):
datacommons admin migrate-db

# Non-interactive / CI/CD mode (auto-approves pending migrations):
datacommons admin --project-id my-project --instance-name my-instance migrate-db -y
```

Key Options:
- `-y`, `--yes`: Automatically confirm and apply pending migrations without interactive prompts.

#### `datacommons admin seed-db`
Seeds baseline geographic nodes and schema mappings on Cloud Spanner via the Ingestion Helper service.

```bash
datacommons admin seed-db
# Or via remote state:
datacommons admin --project-id my-project --instance-name my-instance seed-db
```

#### `datacommons admin ingest start`
Triggers an asynchronous data ingestion workflow using Google Cloud Workflows and Cloud Run. Prints the execution ID and a direct Google Cloud Console link for live monitoring.

```bash
datacommons admin ingest start --imports <import_name>
# Or via remote state:
datacommons admin --project-id my-project --instance-name my-instance ingest start --imports un_sdg
```

Key Options:
- `--imports TEXT` *(required)*: Comma-separated names of the configured imports to run.

#### `datacommons admin ingest show-config`
Fetches and inspects the active environment variables and configuration for the Cloud Run ingestion job.

```bash
datacommons admin ingest show-config
# Or via remote state:
datacommons admin --project-id my-project --instance-name my-instance ingest show-config
```

---

## Data Commons CLI Cheatsheet

### Quickstart Workflow
```bash
# 1. Scaffold Terraform configuration
datacommons admin init --project-id my-project --instance-name prod

# 2. Deploy infrastructure
cd prod
terraform init
terraform apply

# 3. Initialize database & seed baseline data
datacommons admin init-db

# 4. Trigger data ingestion
datacommons admin ingest start --imports my_import
```

### Remote / CI/CD Operations Cheatsheet
```bash
# Run migrations non-interactively without local Terraform files
datacommons admin --project-id my-project --instance-name prod migrate-db -y

# Re-seed Spanner database from anywhere
datacommons admin --project-id my-project --instance-name prod seed-db

# Trigger ingestion using an explicit GCS state URI
datacommons admin --tf-state-location gs://my-project-prod-tfstate/terraform/state/prod/default.tfstate ingest start --imports my_dataset

# Inspect ingestion job configuration
datacommons admin --project-id my-project --instance-name prod ingest show-config
```

---

License: [Apache-2.0](https://github.com/datacommonsorg/datacommons/blob/main/LICENSE)
