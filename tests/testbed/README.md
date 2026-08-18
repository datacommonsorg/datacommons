# Data Commons Platform (DCP) — Developer Testbeds

## 🎯 Overview

DCP Testbeds (e.g. `testbed-1`, `testbed-2`) are shared, pre-warmed Google Cloud environments running in the **`datcom-dcp`** project.

They allow any engineer on the team to **deploy and test custom container builds or release candidates in under 2 minutes** without having to provision cloud infrastructure from scratch or copy API keys.

---

## 🏗 Architecture

```
                     ┌──────────────────────────────────────────────┐
                     │          GCP Project: datcom-dcp             │
                     │  - Secret Manager: dcp-testbed-1-tfvars     │
                     │  - GCS Remote State: tf-state-testbed-1-... │
                     │  - Workflow Service Account (TokenCreator)   │
                     │  - Cloud Run, Spanner DB, Networking         │
                     └──────────────────────┬───────────────────────┘
                                            │
               ┌────────────────────────────┴────────────────────────────┐
               │                                                         │
       1. Connect & Sync                                         3. Push & Persist
   `./tests/testbed/connect.sh connect`                      `./tests/testbed/connect.sh push-config`
   - Pulls tfvars from Secret Manager                        - Saves updated tfvars back to
   - Configures remote backend state                           Secret Manager so the whole team
   - Configures SA Impersonation for CLI                       stays in sync.
   - Sets up `workspaces/testbed-1`
```

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

### Step 1: Connect to a Testbed

Run the connect script from the repository root:

```bash
# Connect directly to testbed-1:
./tests/testbed/connect.sh connect --instance testbed-1

# OR run interactively to choose from available testbeds:
./tests/testbed/connect.sh connect
```

**What the script does automatically:**
1. **Pulls Configuration:** Fetches `dcp-testbed-1-tfvars` from GCP Secret Manager.
2. **Wires Remote State:** Points Terraform backend to `gs://tf-state-testbed-1-datcom-dcp`.
3. **Initializes Workspace:** Scaffolds and runs `terraform init` inside `tests/testbed/workspaces/testbed-1/`.
4. **Configures IAM Impersonation:** Grants your user account `roles/iam.serviceAccountTokenCreator` on the testbed's Ingestion Workflow Service Account so you can run `datacommons` CLI commands seamlessly.

---

### Step 2: Override Container Images or Versions

You are now inside your workspace (`tests/testbed/workspaces/testbed-1/`).

Open `terraform.tfvars` in your editor. At the bottom of the file, uncomment the override for the image or version you want to test:

```hcl
# =============================================================================
# DEVELOPER TESTBED OVERRIDES
# =============================================================================

# --- Option A: Test a platform version tag across all services ---
# dcp_version = "1.1.2-rc1"

# --- Option B: Test granular custom container builds ---
# 1. Main Data Commons Web & Serving Service:
datacommons_services_image = "gcr.io/datcom-ci/datacommons-services:my-feature-branch"

# 2. Ingestion Helper API Service:
# ingestion_helper_service_image = "gcr.io/datcom-ci/datacommons-ingestion-helper:my-fix"

# 3. Ingestion Preprocessing Cloud Run Job:
# ingestion_preprocessing_job_image = "gcr.io/datcom-ci/datacommons-preprocessing:my-job"

# 4. Ingestion Postprocessing Cloud Run Job:
# ingestion_postprocessing_job_image = "gcr.io/datcom-ci/datacommons-postprocessing:my-job"

# 5. Dataflow Flex Template (same bucket, custom template filename):
# ingestion_dataflow_template_gcs_path = "gs://datcom-templates/templates/flex/ingestion-custom-name.json"
```

Apply your changes to GCP:

```bash
terraform apply
```
*Terraform will roll out a new Cloud Run revision with your custom image in ~60–90 seconds.*

---

### Step 3: Running CLI Commands (Service Account Impersonation)

To execute CLI commands against this testbed, run them using `uv` or your virtual environment:

```bash
# Execute commands via uv (Recommended):
uv run datacommons <command> ...

# Or if installed in your activated virtual environment:
datacommons <command> ...
```

The CLI automatically impersonates the testbed's ingestion workflow service account using the TokenCreator IAM role that `connect.sh` configured in Step 1.

If you ever need to manually bind the impersonation permission for a teammate:
```bash
# 1. Get the service account email from your workspace:
terraform output ingestion_workflow_service_account_email

# 2. Bind the TokenCreator role:
gcloud iam service-accounts add-iam-policy-binding "SERVICE_ACCOUNT_EMAIL" \
  --member="user:YOUR_USER_ACCOUNT" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project="datcom-dcp"
```

---

### Step 4: Persisting Configuration (`push-config`)

If you want your updated configuration or image to remain the **shared baseline** for the testbed:

```bash
../../connect.sh push-config --instance testbed-1
```

**When to push:**
* After verifying a release candidate or stable container image that should stay deployed.
* After adding or rotating a shared testbed variable.

**When NOT to push:**
* If you were only running a temporary, one-off test. (In that case, revert your local edit in `terraform.tfvars` and run `terraform apply` to restore the baseline).

---

## 🔍 Discovery & Status

### List All Registered Testbeds
```bash
./tests/testbed/connect.sh list
```
Displays all registered testbed secrets in `datcom-dcp` and allows interactive selection to connect immediately.
