---
name: dcp-setup
description: Procedural guide and strict agent safety guidelines for provisioning a new or existing Data Commons Platform (DCP) instance. Enforces absolute transparency, explicit user approval gates, and interactive param harvesting.
---

# Data Commons Platform Setup (dcp-setup)

This skill guides an agentic coding assistant through the setup and provisioning of a Data Commons Platform (DCP) instance on Google Cloud Platform (GCP).

> [!IMPORTANT]
> **CRITICAL COMPLIANCE DIRECTIVE: USER CONTROL & TRANSPARENCY**
> * The agent must **NEVER** silently automate or submit interactive inputs to CLI commands running in the background (no silent pipelines).
> * The agent must **NEVER** create or modify GCP resources (GCS buckets, Spanner, Cloud Run) without first explaining the exact proposed action and waiting for explicit verbal confirmation.
> * Before executing *any* command, the agent must present the proposed command line to the user and ask for confirmation.
> * **After executing any command**, the agent must immediately provide a clear, useful summary of exactly what was done, what resources were created/changed, and what status or outputs were returned.
> * **GCP Console Deep-Links**: Whenever a resource is created or modified, the agent must construct and print the direct Google Cloud Console deep-links (e.g. GCS browser, Spanner console, Cloud Run dashboard) to enable instant user verification and audit.

---

## Phase 1: Prerequisites Verification & Installation

Before running any setup tasks, the agent must verify that all required local dependencies are installed and authenticated.

### 1. OS Detection & Shell Verification
* Detect the host operating system (macOS vs. Linux).
* Ensure the execution environment has standard terminal tools like `curl`, `unzip`, and shell capabilities.

### 2. CLI Dependencies Check & Local Virtual Env Setup
Verify the availability of `uv`, `terraform`, and `gcloud` by running version checks. If any tool is missing, present a summary to the user and ask if they want the agent to install it automatically:

* **`uv` (Python Package Manager)**:
  * *Check*: `uv --version`
  * *Action if missing*: Ask the user for permission to install it via:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

* **Permanent Workspace CLI Installation**:
  * Inform the user that a workspace-local virtual environment will be created to avoid slow `uvx` downlads.
  * Ask for approval, then run:
    ```bash
    uv venv
    uv pip install "git+https://github.com/datacommonsorg/datacommons.git@main#subdirectory=packages/datacommons-cli"
    ```
  * **Mandatory Tool Call**: For all subsequent steps, invoke the CLI instantly using `uv run datacommons` to prevent execution delays.

* **`terraform` (Infrastructure as Code)**:
  * *Check*: `terraform -version`
  * *Action if missing*: Present the proposed installation command (macOS Homebrew or Linux apt) and wait for approval before running.

* **`gcloud` (Google Cloud SDK)**:
  * *Check*: `gcloud --version`
  * *Action if missing*: Guide the user through the official installer, explaining exactly what package to download.

### 3. GCP Authentication Check
* **Verify active login**: Run `gcloud auth list`. 
* **Re-authenticate if needed**: If no active Application Default Credentials (ADC) are found, inform the user and ask for approval to trigger:
  ```bash
  gcloud auth application-default login
  ```
  Explain that an interactive browser window will open for authentication.

---

## Phase 2: Scaffolding & Configuration Validation (User Approval Gates)

The agent must guide the user through the scaffolding phase with complete transparency, prompting for every parameter.

### 1. Parameter Harvesting with Smart Environment Defaults
Before running the scaffold generator, the agent **MUST run discovery checks to harvest environment defaults, and then present them to the user for explicit confirmation or modification**:

1. **GCP Project ID**:
   * *Discovery*: Run `gcloud config get-value project 2>/dev/null`.
   * *Prompt*: *"I detected that your active Google Cloud project context is set to `[detected_project_id]`. Would you like to use this project for deployment, or would you prefer to specify a different GCP project ID?"*
2. **Namespace**:
   * *Discovery*: Query system username (via `$USER`) or folder name.
   * *Prompt*: *"What unique namespace identifier should we use for this environment? [Default: dcp-$USER]"*
3. **Data Commons API Key**:
   * *Discovery*: Check active environment variables (`echo $DC_API_KEY` or `$MIXER_API_KEY`).
   * *Prompt*: If found: *"I detected a `DC_API_KEY` environment variable in your active session. Should I use this key, or would you like to provide a different one?"*
   * If not found: *"I did not detect a `DC_API_KEY` in your active environment. Please provide a valid API Key from apikeys.datacommons.org (or let me know if we should use a dummy key 'fake-key' for this scaffolding phase)."*

**Wait for the user's explicit confirmation or custom inputs for all three parameters.**


### 2. Scaffolding Generation (Explicit Step)
Once parameters are harvested, present the command and the inputs to the user:
* *"I am going to run `uv run datacommons admin init` to generate your Terraform templates and set up your remote GCS state bucket. The parameters I will submit are Project: [project_id], Namespace: [namespace], and API Key: [api_key]. Do you approve?"*
* **Do not run the command in the background silently.** Run it with explicit inputs so that the command executes without prompting in the background:
  ```bash
  # Force inputs non-interactively to prevent silent background prompt automation
  uv run datacommons admin init --project=[project_id] --namespace=[namespace] --key=[api_key] --auto-approve
  ```

### 3. Variable Verification
* Read `terraform.tfvars` and show the user the generated configuration variables.
* Confirm if they want to make any manual adjustments (e.g., changing machine sizes or regions) before proceeding.

---

## Phase 3: Existing GCP Project & Conflict Validation

Because the partner might deploy to a shared or pre-existing GCP project, the agent must actively identify and resolve resource conflicts, keeping the user fully informed.

### 1. GCP Project Verification
Set the active project context and verify access:
```bash
gcloud config set project [PROJECT_ID]
```

### 2. Enable Required GCP APIs
List the necessary APIs (Spanner, Cloud Run, Secret Manager, Artifact Registry) and ask for approval to enable them:
```bash
gcloud services enable spanner.googleapis.com run.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com iamcredentials.googleapis.com
```

### 3. Spanner Database Conflict Check
* Run `gcloud spanner instances list --project=[PROJECT_ID]` to check if the configured `dcp_spanner_instance_id` already exists.
* **If it exists, report immediately**:
  > ⚠️ **Existing Spanner Instance Detected**: The instance ID `[dcp_spanner_instance_id]` already exists in GCP project `[project_id]`.
  > * **Reusing** this instance may overwrite existing database tables.
  > * **Creating a new one** requires modifying `terraform.tfvars` to use a unique instance ID.
  >
  > *Please tell me how you want to proceed: [Option A: Reuse Instance] or [Option B: Configure New Unique ID].*

---

## Phase 4: Dry-Run & IaC Provisioning (Gate 1 Approval)

Before applying infrastructure changes, compile the exact plan and require verbal user approval.

### 1. Terraform Initialization
Explain and run:
```bash
terraform init
```

### 2. Generate the "Impact Report" (Gate 1 Approval)
Run `terraform plan` and output the changes to a temporary file. Parse this plan to build a detailed **Impact Report** containing:
* **Resources to Create**: List of added resources (e.g. GCS buckets, Spanner instance, Secret Manager keys).
* **Resources to Modify**: List of changed settings.
* **Resources to Destroy**: 🚨 Explicit warnings if any existing resources are set to be destroyed.
* **Estimated Cost Category**: Indicate if it uses production-scale Spanner nodes or budget-friendly processing units.

**Do not run `terraform apply` until the user reviews the Impact Report and replies with explicit verbal approval (e.g., "Yes", "Approve").**

### 3. Apply Infrastructure Changes
Upon receiving approval, execute the deployment:
```bash
terraform apply -auto-approve
```
Display the outputs to the user, highlighting `data_bucket_name` and `cloud-run-service-name`.

---

## Phase 5: IAM Role Impersonation & Latency Polling

### 1. Bind Token Creator Role
Explain that the user must be bound to the newly created service account to initialize the database:
```bash
gcloud iam service-accounts add-iam-policy-binding [dcp_orchestrator_service_account_email] \
    --member="user:[active-gcloud-user]" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --project=[project_id]
```

### 2. Active IAM Propagation Polling (Safety Gate)
Inform the user that GCP IAM replication can take a few minutes. Run a visible loop that checks impersonation status every 15 seconds, showing a progress indicator so the user knows the status.

---

## Phase 6: Flexible Data Loading & Database Initialization

The database seed step should accommodate the partner's custom data rather than defaulting to hardcoded UN-centric files.

### 1. Custom Data Path Selection
Ask the user for their ingestion data source:
* **Option A: Local Folder**: Copy local CSV/JSON files to GCS:
  ```bash
  gcloud storage cp -R ./data/* "gs://[data_bucket_name]/[gcs_data_bucket_input_folder]/"
  ```
* **Option B: Custom GCS Source**: Sync from an existing external GCS bucket:
  ```bash
  gcloud storage cp -R gs://[custom-source-path]/* "gs://[data_bucket_name]/[gcs_data_bucket_input_folder]/"
  ```
* **Option C: Default Sandbox Data**: Copy standard Data Commons public sandbox files for a quick test.

### 2. Initialize Spanner Tables (init-db)
Explain that we are initializing the Spanner schema tables and run:
```bash
uv run datacommons admin init-db
```

### 3. Start the Ingestion Job
Present the command to trigger the Cloud Run pipeline to ingest the data:
```bash
uv run datacommons admin ingest start
```
* **Provide Console Links**: Print the printed **Job Console Link** clearly in the chat so the user can watch the live logs in their browser console.

---

## Phase 7: Health Verification & Local Proxy

Verify that the entire platform is healthy and operational.

### 1. Local Cloud Run Proxy
Establish a local proxy tunnel in the background to expose the Cloud Run Website service:
```bash
gcloud run services proxy [cloud-run-service-name] \
    --project=[project_id] \
    --region=us-central1
```

### 2. Automatic Health Check (Gate 2 Verification)
Show the user you are running automated health tests:
* Hit the `/healthz` endpoint and report the HTTP status code.
* Run a test query to verify the V2 API and present the JSON response.

---

## Phase 8: Operations Handoff

1. **Write Audit Log**: Append a record to `ops_audit_log.md` with timestamps, active project, and success statuses of the setup phases.
2. **Provide Dashboard Links**: Output the direct GCP Console URLs for:
   * Spanner Database Console
   * Cloud Run Service Logs
3. **Instruct Transition**: Present the operational options and advise the user:
   > 🎉 **DCP Bootstrap Setup Complete!**
   > Your Data Commons Platform is fully provisioned and serving custom data on `http://127.0.0.1:8080/`.
   > For all future day-to-day modifications, schema upgrades, and ingestion runs, please load and execute the **`dcp-ops`** skill!
