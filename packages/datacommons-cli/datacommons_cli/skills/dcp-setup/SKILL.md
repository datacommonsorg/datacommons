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
> * **Interactive Selection Gates (Mandatory Tool Call)**: For all user approval gates, resource configuration decisions, and options (such as Spanner instance reuse, ingress privacy, and BigQuery slot reservations), **if the agent's active platform equips it with an interactive questionnaire tool (like `ask_question`), the agent MUST invoke that tool** to present the choices dynamically in the client UI instead of requesting the user to manually type their response. Only print plain text options if no such tool is supported by the active platform.
> * **Clickable File Links (UX Requirement)**: Whenever referring to a local file or directory (such as `terraform.tfvars` or the project workspace folder), the agent **MUST** format it as a clickable Markdown link using its absolute file path: `[filename](file:///absolute/path/to/file)`. Never print plain-text filenames.
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

### 1. Parameter Harvesting with Environment Defaults
Before running the scaffold generator, the agent **MUST first run discovery checks to harvest default configuration settings, present them as a neat list, and prompt the user for their choice**:

* **Environment Discoveries**:
  1. **GCP Project ID**: Run `gcloud config get-value project 2>/dev/null`.
  2. **Namespace**: Query system username (via `$USER`) or directory folder name.
  3. **Data Commons API Key**: Check active environment variables (`echo $DC_API_KEY` or `$MIXER_API_KEY`).

* **Interactive Choice (UI Recommendation)**: Present the harvested defaults and explicitly prompt the user:
  > *"Would you like to proceed with these default configuration settings, or would you prefer to customize specific variables?"*
  * **Option A: Proceed with Defaults**: Directly write the defaults to `terraform.tfvars`, asking only for any required credentials that are missing (like a blank Project ID), and proceed straight to the dry-run plan.
  * **Option B: Customize Specific Settings**: Sequentially prompt for Project ID, Custom Namespace overrides, and API Keys.

* **Mandatory Context Block**: Before executing the scaffolding generator (or any major infrastructure phase), the agent **MUST** print a highly concise blockquote headered **`### Context`**, using empty blockquote lines (`>`) to ensure clean vertical formatting:
  * **What**: What the step/command does.
  * **Why**: Why this is architecturally necessary.
  * **Where**: Where in their directory structure they can inspect or customize the resources.


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
  * Ask the user explicitly in the chat (leveraging the `ask_question` selection tool): *"Would you like to make your Custom Data Commons website publicly accessible to the open internet (best for sharing and quick testing), or keep it private and secured behind IAM OIDC authentication (default, best for secure enterprise data)?"*
  * **Action & Approval Gate**: Once the choice is selected, **the agent must explain the changes, present the proposed modifications as a clean file diff block, ask for explicit verbal approval, and write the update to `terraform.tfvars` only upon receiving approval.**
    * **If Public**: uncomment `datacommons_services_allow_unauthenticated_access = true`.
    * **If Private/Default**: ensure it remains commented out or set to `false`.
* **Explicit Google Maps API Key Choice Heuristic (Mandatory Prompt)**:
  * The agent must inspect `terraform.tfvars` for Google Maps credentials.
  * If `auth_google_maps_api_key` is set to `"TODO"` and `auth_create_google_maps_api_key` is set to `false`, the agent **must explicitly prompt the user in the chat (leveraging the `ask_question` tool)**:
    * *"A valid Google Maps API key is required for using Data Commons. How would you like to proceed?"*
    * **Option 1: Use Existing Key**: Ask the user to provide their existing Maps API key string.
    * **Option 2: Auto-generate restricted key**: Ask the user if they want Terraform to create a new restricted key natively.
  * **Action & Approval Gate**: Once the option is selected, **the agent must explain the changes, present the proposed modifications as a clean file diff block, ask for explicit verbal approval, and write the variables to `terraform.tfvars` only upon receiving approval.**
* Confirm if the user wants to make any other manual adjustments (e.g., changing machine sizes or regions) before proceeding.

---

## Phase 3: Existing GCP Project & Conflict Validation

Because the partner might deploy to a shared or pre-existing GCP project, the agent must actively identify and resolve resource conflicts, keeping the user fully informed.

### 1. GCP Project Verification
* **Action & Approval Gate**: Explain that the active project context needs to be set to `[project-id]`. Present the proposed command, ask for explicit verbal approval, and execute **only** upon receiving approval:
  ```bash
  gcloud config set project [project-id]
  ```

### 2. Spanner Instance Discovery & Proactive Configuration (Step 1)
* **Mandatory Order**: This check must be executed and finalized *before* initiating the BigQuery check.
* **Action & Approval Gate**: Explain that we need to query active Spanner database instances on GCP to check for name conflicts or reuse opportunities. Present the proposed command, ask for explicit verbal approval, and execute **only** upon receiving approval:
  ```bash
  gcloud spanner instances list --project=[project-id]
  ```
* **If active Spanner instances are found**:
  * Present the list clearly to the user in the chat, and explicitly prompt them (leveraging the `ask_question` tool if available):
    > 🔍 **Active Spanner Instances Discovered**:
    > I found these active Spanner instances in project `[project-id]`:
    > 1. `dcp-shared-spanner-instance`
    > 2. `dcp-instance-dev`
    > ...
    > Would you like to:
    > * **Option A: Reuse an existing instance**? (Highly Recommended to save project capacity and costs).
    > * **Option B: Create a brand-new Spanner instance**? (Will generate `[namespace]-dc-instance` and increase project billing).
  * **Action & Approval Gate**: Once the option is selected, **the agent must explain the changes, present the proposed modifications as a clean file diff block, ask for explicit verbal approval, and write the update to `terraform.tfvars` only upon receiving approval.**
    * **If Option A (Reuse)**: set `spanner_create_instance = false` and `spanner_instance_id = "[chosen_instance_id]"`.
    * **If Option B (Create New)**:
      * **Display Name Length Safety Check**: Calculate the resulting display name length: `${namespace}-${spanner_instance_id}`.
      * If this length exceeds the GCP limit of **30 characters** (e.g., `dcp-keyurs-dcp-keyurs-dc-instance` is 34 characters):
        * Prompt the user immediately with a warning and recommend a shortened `spanner_instance_id` like `dc-inst` so the resulting name (`[namespace]-dc-inst`) remains safe under 30 characters.
      * Once the shortened name is verified, present the proposed HCL diff block, ask for approval, and set `spanner_create_instance = true` and `spanner_instance_id = "[chosen_shortened_instance_id]"`.
* **If no active Spanner instances are found**:
  * **Action & Approval Gate**: Explain that a new database instance will be created. Present the proposed modifications as a clean file diff block, ask for explicit verbal approval, and write `spanner_create_instance = true` and `spanner_instance_id = "[namespace]-dc-inst"` to `terraform.tfvars` **only** upon receiving approval.

* **Wait for Spanner configuration to be finalized and written before moving to the next step.**

### 3. BigQuery Slot Reservation Conflict Check (Step 2)
* **Mandatory Order**: Initiate this check *only* after the Spanner configuration above is fully completed and written to disk.
* **Retrieve Target Region**: Parse the `region` variable from `terraform.tfvars` or `variables.tf` (defaulting to `us-central1` if it is commented out or blank). Use this string as the target `[region]` location.
* **Action & Approval Gate**: Explain that we need to check for existing BigQuery slot reservations in the target region to avoid provisioning conflicts. Present the proposed command, ask for explicit verbal approval, and execute **only** upon receiving approval:
  ```bash
  bq ls --reservation --project_id=[project-id] --location=[region]
  ```
* **If a reservation named `default` already exists**:
  * Present this discovery to the user and explain that we should reuse it to save slots.
  * **Action & Approval Gate**: Present the proposed modifications as a clean file diff block, ask for explicit verbal approval, and write `spanner_create_bigquery_reservation = false` to `terraform.tfvars` **only** upon receiving approval.
* **If no `default` reservation is found**:
  * Inform the user that no reservation was found, and ask if they want to create a new one or reuse an existing one.
  * **Action & Approval Gate**: Once selected, present the proposed modifications as a clean file diff block, ask for explicit verbal approval, and write the variables to `terraform.tfvars` **only** upon receiving approval.
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

### 3. User-Led Infrastructure Provisioning (Gate 2 Hand-Off)
* **Strict Compliance Directive**: The agent **must never** execute `terraform apply` automatically or in the background. It must hand over execution control directly to the developer.
* **Set Time and Component Expectations**: Explain to the developer that `terraform apply` is a long-running operation taking **10 to 15 minutes or longer** depending on the size of the custom dataset. Outline the physical execution phases:
  * **Infrastructure Provisioning**: Creating the Spanner instance, Secret Manager secrets, and Cloud Run serving container/API gateway proxy revisions.
  * **Data Pre-processing**: Spinning up the stager container to parse local CSV datasets, index observations into SQLite databases, and compile JSON-LD graph shards.
  * **Parallel Database Seeding**: Triggering Cloud Workflows and deploying Apache Beam parallel Dataflow templates to load mutations and build Spanner indexes.
* **Mandatory Context Block**: Print a highly concise blockquote headered **`### Context`**, using empty blockquote lines (`>`) to ensure clean vertical formatting:
  * **What**: What `terraform apply` is creating.
  * **Why**: Why this multi-layer cloud architecture is required to serve Custom Data Commons SPARQL queries securely and at scale.
  * **Where**: Where they can review the module definitions in `/infra/dcp/modules/`.
* **Instruct Execution**: Advise the developer to run this command in their terminal:
  ```bash
  terraform apply
  ```

### 4. Conditional Telemetry Tracking (Timing Guard)
* **The Timing Guard**: The agent must **only** start telemetry after the developer has actively kicked off the command. It must ask:
  > *"Please run `terraform apply` in your terminal. **Once you have actively kicked off the command**, you can steer my tracking in one of two ways:*
  > * 📊 **If you want me to actively monitor progress**: Reply to me with **`\"Start monitoring\"`** and I will register background polling loops to track your GCS uploads, Workflows executions, and Dataflow Loader jobs reactively!
  > * ⚙️ **If you prefer to run it independently**: Simply let me know **once the command has finished successfully** (so we can proceed to the verification steps), or **if you run into any issues** (so we can troubleshoot)."*
* **Safety poller activation**:
  * **If `"Start monitoring"` is requested**: Immediately register the `schedule` progress checking task.
  * **Otherwise**: Go to sleep immediately without registering a timer, waiting for the user's next manual update.

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
Inform the user that GCP IAM replication can take a few minutes. The agent **MUST** run a visible, non-blocking loop using the **Exponential Backoff Polling Heuristics** (checking at 10s, 20s, 40s, and then scaling up to a maximum quiet heartbeat of 60s), **outputting the compact, headerless 2-column progress table at every single heartbeat check** to show elapsed time, current state, and prevent redundant conversational filler.

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
