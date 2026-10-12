# Data Commons Platform (DCP) — Developer Testbeds

## Overview

DCP Testbeds (e.g. `testbed-1`, `testbed-2`) are shared, pre-warmed Google Cloud environments running in the **`datcom-dcp`** project.

They allow any engineer on the team to **deploy and test custom container builds or release candidates in under 2 minutes** without having to provision cloud infrastructure from scratch or copy API keys.

---

## How It Works

A testbed pairs a **remote GCP environment** in `datcom-dcp` with a **local workspace** on your machine (`tests/testbed/workspaces/<instance>/`).

All lifecycle operations are managed using `./tests/testbed/fetch_terraform_state.sh`:

| Subcommand | Action | Data Flow |
| :--- | :--- | :--- |
| **`connect`** | Sets up your local workspace, wires remote GCS state, configures module sources, and checks IAM permissions. | **Cloud $\to$ Local**<br>(Secret Manager $\to$ `terraform.tfvars`) |
| **`push-config`** | Promotes your local `terraform.tfvars` to the team's shared baseline secret. | **Local $\to$ Cloud**<br>(`terraform.tfvars` $\to$ Secret Manager) |
| **`list`** | Lists all active testbeds in the GCP project. | **Cloud $\to$ Terminal** |

---

## Prerequisites

1. **Google Cloud SDK (`gcloud`)** authenticated with access to `datcom-dcp`:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

2. **Terraform (`>= 1.5.0`)** installed:
   ```bash
   terraform -version
   ```

---

## Step-by-Step Developer Workflow

> Adding a **brand-new** testbed instead of using an existing one?
> See [CREATING_A_TESTBED.md](./CREATING_A_TESTBED.md).

### Step 1: Connect to a Testbed

Run the connect script from the repository root, choosing where the Terraform modules and `workflow.yaml` come from:

```bash
# Option A: Connect and pin modules to an official release tag (e.g. v1.1.5):
./tests/testbed/fetch_terraform_state.sh connect --instance testbed-1 --terraform-modules-source v1.1.5

# Option B: Connect and use your local modules / workflow.yaml (Default):
./tests/testbed/fetch_terraform_state.sh connect --instance testbed-1 --terraform-modules-source local
```

*(You can browse all published release tags on the [GitHub Tags Page](https://github.com/datacommonsorg/datacommons/tags). Tags follow the `vX.Y.Z` format, like `v1.1.5`).*

**What `connect` does automatically:**
1. **Pulls Configuration:** Fetches `dcp-testbed-1-tfvars` from Secret Manager into `tests/testbed/workspaces/testbed-1/terraform.tfvars`. *(If you already have local edits, it prompts before overwriting).*
2. **Sets Module Source:** Wires `main.tf` to pull from GitHub at your chosen tag, or symlinks to your local `infra/dcp/modules`.
3. **Wires Remote State:** Points Terraform backend to `gs://tf-state-testbed-1-datcom-dcp`.
4. **Initializes Workspace:** Runs `terraform init -upgrade` inside `tests/testbed/workspaces/testbed-1/`.
5. **Configures IAM & Spanner Permissions:** Grants your user account:
   - `roles/spanner.databaseAdmin` and `roles/spanner.databaseUser` on the Spanner instance to run `datacommons admin init-db` and `migrate-db` directly.
   - `roles/iam.serviceAccountTokenCreator` on the Ingestion Workflow Service Account to trigger `datacommons admin ingest start`.

---

### Step 2: Edit `terraform.tfvars` and Apply

You are now inside your workspace (`tests/testbed/workspaces/testbed-1/`).

Open `terraform.tfvars` in your editor to configure the version or container image you want to test:

```hcl
# Test a baseline release version across all services:
dcp_version = "1.1.5"

# OR test a custom container build:
datacommons_services_image = "gcr.io/datcom-website-dev/datacommons-services:my-feature-tag"
```

The full list of testbed overrides lives in [`testbed_overrides.tfvars.template`](./testbed_overrides.tfvars.template).

Inspect and apply your changes to GCP:

```bash
cd tests/testbed/workspaces/testbed-1
terraform plan
terraform apply
```
*Terraform will roll out a new Cloud Run revision with your custom image in ~60–90 seconds.*

---

### Step 3: Running CLI Commands

To execute CLI commands against this testbed, run them using `uv` or your virtual environment:

```bash
# Execute commands via uv (Recommended):
uv run datacommons <command> ...

# Or if installed in your activated virtual environment:
datacommons <command> ...
```

* **Database Operations (`init-db`, `migrate-db`)**: Run directly against Cloud Spanner using your authenticated End-User Credentials (EUC).
* **Ingestion Workflows (`ingest start`)**: Automatically impersonates the testbed's ingestion workflow service account via `TokenCreator`.

---

### Step 4: Persisting Configuration (`push-config`)

If you want your updated configuration or image to remain the **shared baseline** for the testbed:

```bash
./tests/testbed/fetch_terraform_state.sh push-config --instance testbed-1
```

**When to push:**
* After verifying a release candidate or stable container image that should stay deployed for the team.
* After adding or rotating a shared testbed variable.

**When NOT to push:**
* If you were only running a temporary, one-off test. (In that case, simply do not run `push-config`).

---

## Discovery & Status

### List All Registered Testbeds
```bash
./tests/testbed/fetch_terraform_state.sh list
```
Displays all registered testbed secrets in `datcom-dcp` and allows interactive selection to connect immediately.
