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
> * **Interactive Selection Gates (UI Recommendation)**: For all user approval gates, resource configuration decisions, and options (such as Spanner instance reuse, ingress privacy, and BigQuery slot reservations), the agent should leverage interactive UI selectors or structured multi-choice questionnaire tools (such as `ask_question` if supported by the platform) to present clean, selectable options in the client instead of requesting the user to manually type their response.
> * Before executing *any* command, the agent must present the proposed command line to the user and ask for confirmation.
> * **After executing any command**, the agent must immediately provide a clear, useful summary of exactly what was done, what resources were created/changed, and what status or outputs were returned.
> * **GCP Console Deep-Links**: Whenever a resource is created, modified, or queried, the agent must **generously construct and print direct GCP Console deep-links** (such as Spanner database tables, GCS folder paths, Cloud Run metrics, Cloud Workflows executions, and Dataflow pipeline graphs) to enable the user to instantly inspect and audit the live resources by themselves at any time.
> * **Active Progress Updates (Mandatory Heartbeat Feedback)**: During long-running operations (such as `terraform apply` or data ingestion pipelines), the agent must never go completely silent. **At every single heartbeat check (checking at 10s, 20s, 40s, and then scaling up to a maximum quiet heartbeat of 60s), the agent MUST output the highly-condensed 2-column progress table directly into the chat** to provide constant, reassuring visual feedback.
>   * **Structured Progress Layout (Compact 2-Column Table)**: All progress checks must be formatted in a clean, headerless, 2-column Markdown table (with values wrapped in inline backticks to render as yellow/amber pills):
>     | | |
>     | :--- | :--- |
>     | **Phase** | `Phase X/3: [Global Phase Name]` |
>     | **Status** | `[Factual, highly-condensed numerical metrics/counters]` |
>     | **Elapsed** | `[phase_time] (Total pipeline time: [total_ingestion_time])` |
>   * **Silent Scheduler & Mandatory Timer Registration**: Schedulers are silent (do not print closing conversational filler like "Scheduling a 30-second timer now..."), but **the agent MUST strictly register a progress timer using the `schedule` tool at the end of every single turn** during background monitoring, and then immediately end its turn by calling no more tools. Doing so ensures the system reactively wakes the agent up in a new turn to push the next progress card automatically. **Never go to sleep without an active scheduled timer!**
>   * **Unified Ingestion Phase Labeling**:
>     * 🛠️ **Phase 1 of 3: Preprocessing Container**
>       * *Sub-stage 1/3 (CSV Import)*: `Status: Sub-stage 1/3 - CSV Import: 62.6% (979 / 1,562 files processed)`
>       * *Sub-stage 2/3 (Indexing)*: `Status: Sub-stage 2/3 - Database Indexing: Indexing 13.9M observations`
>       * *Sub-stage 3/3 (Export)*: `Status: Sub-stage 3/3 - JSON-LD Export: Staging 13.98M observations. 41 Node & 318+ Observation shards completed`
>     * 🔗 **Phase 2 of 3: Cloud Workflows Orchestration**
>       * `Status: Container completed successfully. Workflows state machine orchestrating Dataflow trigger`
>     * ⚡ **Phase 3 of 3: Dataflow Parallel Loader**
>       * **Dynamic Spanner Ingest Heuristic**: Extract active mutation metrics: `gcloud beta dataflow metrics list [JOB_ID] --project=[PROJECT_ID] --region=[REGION]`. Look up `mutation_groups_write_success` (staged mutation count) and `spanner_write_latency_ms_MEAN` (average batch latency) and print: `Status: Written graph mutations: [mutation_count] successfully loaded to Spanner (mean batch latency: [latency]ms)`.
>   * Only print a detailed block or link when a **major pipeline transition occurs** or upon final success/failure. **Silent Scheduler Rule**: When scheduling these background timers, the agent must never print redundant closing text (such as "The progress timer is active. I will stand by..."). Simply print the 3-line status update, call the `schedule` tool, and end the turn immediately.
> * **Brevity & Tabular Formatting**: Infrastructure operations require absolute clarity. Avoid verbose, narrative, or flowery summaries. Present complex details (such as configuration changes, resource impacts, plans, or status reports) using clean markdown tables, bullet points, or short, direct facts. Keep narrative text blocks extremely concise.

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

* **Workspace CLI Verification**:
  * Confirm that the workspace-local virtual environment and CLI are fully functional by verifying the help output:
    ```bash
    uv run datacommons --help
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
* *"I am going to run `uv run datacommons admin init` to generate your Terraform templates and set up your remote GCS state bucket. The parameters I will submit are Project ID: [project-id], Namespace: [namespace], and DC API Key: [dc-api-key]. Do you approve?"*
* **Do not run the command in the background silently.** Run it with explicit inputs so that the command executes without prompting in the background:
  ```bash
  # Force inputs non-interactively to prevent silent background prompt automation
  uv run datacommons admin init --project-id=[project-id] --namespace=[namespace] --dc-api-key=[dc-api-key]
  ```

### 3. Variable Verification & Ingress Security Prompt
* Read `terraform.tfvars` and show the user the generated configuration variables.
* **Interactive Ingress Security Choice (Mandatory Prompt)**:
  * Ask the user explicitly in the chat: *"Would you like to make your Custom Data Commons website publicly accessible to the open internet (best for sharing and quick testing), or keep it private and secured behind IAM OIDC authentication (default, best for secure enterprise data)?"*
  * **If Public is selected**: Locate `datacommons_services_allow_unauthenticated_access` inside `terraform.tfvars`, uncomment it, and set it to `true`.
  * **If Private/Default is selected**: Ensure `datacommons_services_allow_unauthenticated_access` remains commented out or set to `false`.
* **Explicit Google Maps API Key Choice Heuristic (Mandatory Prompt)**:
  * The agent must inspect `terraform.tfvars` for Google Maps credentials.
  * If `auth_google_maps_api_key` is set to `"TODO"` and `auth_create_google_maps_api_key` is set to `false`, the agent **must explicitly prompt the user in the chat**:
    * *"A valid Google Maps API key is required for using Data Commons. How would you like to proceed?"*
    * **Option 1: Use Existing Key**: Ask the user to provide their existing Maps API key string. Once provided, the agent must write it directly to `auth_google_maps_api_key` inside `terraform.tfvars`.
    * **Option 2: Auto-generate restricted key**: Ask the user if they want Terraform to create a new restricted key natively. Once approved, the agent must write `auth_create_google_maps_api_key = true` and set `auth_google_maps_api_key = null` inside `terraform.tfvars` so Terraform provisions it securely.
* **BigQuery Post-Processing Check (Mandatory Safeguard)**:
  * Verify the configuration of `ingestion_workflow_enable_bigquery_postprocessing` inside `terraform.tfvars`.
  * **Mandatory Constraint**: Due to active upstream BigQuery federation and post-processing limitations, this variable **MUST be set to `false`** to ensure a stable and successful data ingestion execution.
  * If it is missing, commented out, or set to `true`, the agent must explain this limitation to the user in the chat, ask for approval, and automatically write `ingestion_workflow_enable_bigquery_postprocessing = false` to `terraform.tfvars`.
* Confirm if the user wants to make any other manual adjustments (e.g., changing machine sizes or regions) before proceeding.

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

### 3. Spanner Instance Discovery & Proactive Configuration (Step 1)
* **Mandatory Order**: This check must be executed and finalized *before* initiating the BigQuery check.
* Run `gcloud spanner instances list --project=[PROJECT_ID]` to discover active Spanner resources in the project.
* **If active Spanner instances are found**:
  * Present the list clearly to the user in the chat:
    > 🔍 **Active Spanner Instances Discovered**:
    > I found these active Spanner instances in project `[project_id]`:
    > 1. `dcp-shared-spanner-instance`
    > 2. `dcp-instance-dev`
    > ...
    > Would you like to:
    > * **Option A: Reuse an existing instance (Highly Recommended to save project capacity and costs)**? Please tell me which number/ID to use.
    > * **Option B: Create a brand-new Spanner instance**? (Will generate `[namespace]-dc-instance` and increase project billing).
  * **Action based on Choice**:
    * **If Option A (Reuse)**: Ask the user if they approve, then automatically update `terraform.tfvars` to set `spanner_create_instance = false` and `spanner_instance_id = "[chosen_instance_id]"`. Inform the user once the file is updated.
    * **If Option B (Create New)**:
      * **Display Name Length Safety Check**: Calculate the resulting display name length: `${namespace}-${spanner_instance_id}`.
      * If this length exceeds the GCP limit of **30 characters** (e.g., `dcp-keyurs-dcp-keyurs-dc-instance` is 34 characters):
        * Prompt the user immediately with a warning and recommend a shortened `spanner_instance_id` like `dc-inst` so the resulting name (`[namespace]-dc-inst`) remains safe under 30 characters.
      * Ask the user if they approve the verified setting, then automatically update `terraform.tfvars` to set `spanner_create_instance = true` and `spanner_instance_id = "[chosen_shortened_instance_id]"`. Inform the user once the file is updated.
* **If no active Spanner instances are found**:
  * Automatically update `terraform.tfvars` to set `spanner_create_instance = true` and `spanner_instance_id = "[namespace]-dc-inst"` to ensure a fresh database instance is provisioned cleanly and inform the user.

* **Wait for Spanner configuration to be finalized and written before moving to the next step.**

### 4. BigQuery Slot Reservation Conflict Check (Step 2)
* **Mandatory Order**: Initiate this check *only* after the Spanner configuration above is fully completed and written to disk.
* **Retrieve Target Region**: Parse the `region` variable from `terraform.tfvars` or `variables.tf` (defaulting to `us-central1` if it is commented out or blank). Use this string as the target `[REGION]` location.
* Run a query to check for existing BigQuery reservations in that target region location:
  ```bash
  bq ls --reservation --project_id=[PROJECT_ID] --location=[REGION]
  ```
* **If a reservation named `default` already exists**:
  * Present this discovery to the user and explain that we should reuse it to avoid conflicts and save slots.
  * Upon user confirmation, write/append `spanner_create_bigquery_reservation = false` to `terraform.tfvars` and confirm the write to the user.
* **If no `default` reservation is found**:
  * Inform the user that no reservation was found, and ask if they want to create a new one (sets `spanner_create_bigquery_reservation = true`) or reuse a pre-existing default one if they know it exists.
  * Write the selected value to `terraform.tfvars` and confirm.

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

### 3. Apply Infrastructure Changes & Interactive Fail-safe
Upon receiving approval, execute the deployment:
```bash
terraform apply -auto-approve
```
* **Transient GCP Propagation Fail-safe**:
  * If the deployment fails due to transient GCP resource replication latency (e.g., `404 Instance/Database not found` or `409 Already exists` during IAM database user bindings):
    * **Immediately inform the user of the failure** in the chat.
    * Explain that this is a normal, expected GCP resource replication latency issue, and that the previous plan binary is now stale due to a partial apply.
    * Prompt the user in the chat:
      > 🔄 **GCP Resource Propagation Delay Detected**:
      > The deployment hit a transient GCP replication delay. This is completely normal and expected.
      > Since a partial apply occurred, our old plan is now stale. 
      > * I will compile a fresh plan using `terraform plan -out=tfplan.binary` immediately.
      > * I will then present the new short Impact Report of the remaining resources for your review.
      > * Do you approve compiling the fresh plan and retrying?
    * **Wait for the user's explicit verbal confirmation** before executing the new plan and apply sequence.
* Display the final successful outputs to the user, highlighting `data_bucket_name` and `cloud-run-service-name`.

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
* **Parameter-free Ingestion Warning**: Explain that the `ingest start` command is completely **parameter-free**. It dynamically resolves Cloud Run variables from Terraform outputs, and reads staged config files directly from GCS.
* **Strict Command Constraint**: **NEVER** append flags like `--import-name` or `--import-list` (the pipeline handles this automatically).
* Present the command and trigger:
  ```bash
  uv run datacommons admin ingest start
  ```
* **Provide Console Links**: Print the **Job Console Link** and **Workflow Console Link** clearly in the chat so the user can watch the live executions.

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

1. **Write Audit Log**: Append a record to `dcp_audit_log.md` with timestamps, active project, and success statuses of the setup phases.
2. **Provide Dashboard Links**: Output the direct GCP Console URLs for:
   * Spanner Database Console
   * Cloud Run Service Logs
3. **Instruct Transition**: Present the operational options and advise the user:
   > 🎉 **DCP Bootstrap Setup Complete!**
   > Your Data Commons Platform is fully provisioned and serving custom data.
   > For all future day-to-day data loads, schema modifications, and ingestion runs, please use the standard CLI: `datacommons admin ingest start`!
