# Data Commons Platform (DCP) — Developer Testbeds

## 🎯 Overview

DCP Testbeds (e.g. `testbed-1`, `testbed-2`) are shared, pre-warmed Google Cloud environments running in the **`datcom-dcp`** project.

They allow any engineer on the team to **deploy and test custom container builds or release candidates in under 2 minutes** without having to provision cloud infrastructure from scratch or copy API keys.

---

## How It Works

A testbed pairs a **remote GCP environment** in `datcom-dcp` with a **local workspace** on your machine (`tests/testbed/workspaces/<instance>/`).

All lifecycle operations are managed using `./tests/testbed/fetch_terraform_state.sh`:

| Subcommand | Action | Data Flow |
| :--- | :--- | :--- |
| **`connect`** | Sets up your local workspace, wires remote GCS state, and checks IAM permissions. | **Cloud $\to$ Local**<br>(Secret Manager $\to$ `terraform.tfvars`) |
| **`configure`** | Updates container images, versions, or module sources (Git vs. local), then plans and applies. | **Local $\to$ Cloud**<br>(Workspace $\to$ Cloud Run revision) |
| **`push-config`** | Promotes your local settings to the team's shared baseline. *(Opt-in, default false)* | **Local $\to$ Cloud**<br>(`terraform.tfvars` $\to$ Secret Manager) |

---

## 📋 Prerequisites

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

## 🚀 Step-by-Step Developer Workflow

> Adding a **brand-new** testbed instead of using an existing one?
> See [CREATING_A_TESTBED.md](./CREATING_A_TESTBED.md).

### Step 1: Connect to a Testbed (Read/Attach)

Attach to an existing testbed to download its current baseline configuration:

```bash
# Connect directly to testbed-1:
./tests/testbed/fetch_terraform_state.sh connect --instance testbed-1

# OR run interactively to choose from available testbeds:
./tests/testbed/fetch_terraform_state.sh connect
```

**What `connect` does automatically:**
1. **Pulls Configuration:** Fetches `dcp-testbed-1-tfvars` from GCP Secret Manager into `tests/testbed/workspaces/testbed-1/terraform.tfvars`.
2. **Wires Remote State:** Configures GCS backend state (`gs://tf-state-testbed-1-datcom-dcp`).
3. **Initializes Workspace:** Scaffolds and runs `terraform init`.
4. **Configures IAM Impersonation:** Grants your user account `roles/iam.serviceAccountTokenCreator` on the testbed's Ingestion Workflow Service Account so you can run `datacommons` CLI commands seamlessly.

---

### Step 2: Configure and Deploy (`configure`)

The `configure` command modifies your testbed's orchestration sources, container versions, and image overrides, then plans and applies.

#### Option A: Test a custom container build against a clean release tag (Hermetic Mode)
To ensure no local working tree changes or uncommitted `workflow.yaml` edits leak into the testbed:
```bash
./tests/testbed/fetch_terraform_state.sh configure \
  --instance testbed-1 \
  --terraform-source git \
  --terraform-ref v1.1.5 \
  --dcp-version 1.1.5 \
  --services-image gcr.io/datcom-website-dev/datacommons-services:my-feature-tag \
  --apply
```

#### Option B: Test local Terraform modules and workflow edits (Dev Mode)
To deploy your local working branch's Terraform modules and `workflow.yaml`:
```bash
./tests/testbed/fetch_terraform_state.sh configure \
  --instance testbed-1 \
  --terraform-source local \
  --apply
```

#### Option C: Reset all custom container overrides
To remove all custom `*_image` overrides and restore services to the baseline `dcp_version`:
```bash
./tests/testbed/fetch_terraform_state.sh configure \
  --instance testbed-1 \
  --clear-image-overrides \
  --apply
```

---

### Step 3: Running CLI Commands (Service Account Impersonation)

To execute CLI commands against this testbed, run them using `uv` or your virtual environment:

```bash
# Execute commands via uv (Recommended):
uv run datacommons <command> ...

# Or if installed in your activated virtual environment:
datacommons <command> ...
```

The CLI automatically impersonates the testbed's ingestion workflow service account using the TokenCreator IAM role that `fetch_terraform_state.sh` configured in Step 1.

---

### Step 4: Persisting Configuration (`push-config`)

> [!IMPORTANT]
> Developer experiments and custom container overrides **never mutate the team's shared secret by default**.
> Only push your configuration when you have verified your changes and deliberately want them to become the new baseline for the entire team.

To promote your local configuration to Secret Manager:

```bash
# Explicit standalone command:
./tests/testbed/fetch_terraform_state.sh push-config --instance testbed-1

# OR pass --push-config directly during configure:
./tests/testbed/fetch_terraform_state.sh configure --instance testbed-1 --dcp-version 1.1.5 --apply --push-config
```

The full, authoritative list of testbed overrides lives in [`testbed_overrides.tfvars.template`](./testbed_overrides.tfvars.template).

---

## 🔍 Discovery & Status

### List All Registered Testbeds
```bash
./tests/testbed/fetch_terraform_state.sh list
```
Displays all registered testbed secrets in `datcom-dcp` and allows interactive selection to connect immediately.
