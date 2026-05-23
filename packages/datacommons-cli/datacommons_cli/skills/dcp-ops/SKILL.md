---
name: dcp-ops
description: Procedural guide and strict safety guidelines for managing, upgrading, and maintaining an active Data Commons Platform (DCP) instance. Enforces absolute transparency, step-by-step pacing, and user approval gates.
---

# Data Commons Platform Operations (dcp-ops)

This skill guides an agentic coding assistant through Day-2 administration, data loading, configuration upgrades, and troubleshooting of an existing Data Commons Platform (DCP) instance.

> [!IMPORTANT]
> **CRITICAL COMPLIANCE DIRECTIVE: USER CONTROL & TRANSPARENCY**
> * The agent must **NEVER** silently automate or modify cloud resources (GCS, Spanner, Cloud Run) without explaining the exact proposed changes and waiting for explicit verbal confirmation.
> * Before executing *any* command, the agent must present the proposed command line to the user and ask for confirmation.
> * **After executing any command**, the agent must immediately provide a clear, useful summary of exactly what was done, what resources were changed, and what status or outputs were returned.
> * **GCP Console Deep-Links**: Whenever a resource is created, modified, or queried, the agent must **generously construct and print direct GCP Console deep-links** (such as Spanner database tables, GCS folder paths, Cloud Run metrics, Cloud Workflows executions, and Dataflow pipeline graphs) to enable the user to instantly inspect and audit the live resources by themselves at any time.
> * **Active Progress Updates (Quiet Polling & Percent Spinner)**: During long-running operations (such as `terraform apply` or data ingestion pipelines), the agent must never go silent, but **must avoid noisy output**. Print only a **highly-condensed, 3-line progress block** using **Exponential Backoff Polling Heuristics** (checking at 10s, 20s, 40s, and then scaling up to a maximum quiet heartbeat of 60s for the remainder of the long-running job).
>   * **Structured Progress Layout (Compact 2-Column Table)**: All progress checks must be formatted in a clean, headerless, 2-column Markdown table (with values wrapped in inline backticks to render as yellow/amber pills):
>     | | |
>     | :--- | :--- |
>     | **Phase** | `Phase X/3: [Global Phase Name]` |
>     | **Status** | `[Factual, highly-condensed numerical metrics/counters]` |
>     | **Elapsed** | `[phase_time] (Total pipeline time: [total_ingestion_time])` |
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
> * Keep the user fully informed of background tasks (e.g., logs monitoring, proxy tunnels), providing direct console URLs for observability.

---

## Phase 1: Active Environment Discovery

Before performing any operations, the agent must inspect the current directory to map out the active infrastructure state.

### 1. Verify Active Provisioning
* Verify that `main.tf` and `terraform.tfvars` exist and that a valid Terraform state is present.
* If no infrastructure has been provisioned yet, stop immediately and direct the user to run **`dcp-setup`** first.

### 2. Read Active GCP Project Context
* Parse `terraform.tfvars` to extract `project_id`, `namespace`, and target instance sizes.
* Set the active gcloud project context and show the user:
  ```bash
  gcloud config set project [project_id]
  ```
* Verify the active user has permission to query project services.

---

## Phase 2: Updating System Configuration & Deployments (Gate 1 Approval)

Use this workflow whenever you need to deploy a new Docker image or update configuration variables.

### 1. Edit Configuration
* Instruct the user that we are about to update the configuration.
* Present the proposed modifications inside `terraform.tfvars` (e.g., changing `cdc_web_service_image`, `cdc_data_job_image`, or `gcs_data_bucket_input_folder`) and wait for approval before writing any changes.

### 2. Apply Configuration Changes (Gate 1 Approval)
* Run a dry-run plan to inspect the proposed modifications:
  ```bash
  terraform init  # Confirm plugins are initialized
  terraform plan -out=tfplan.out
  ```
* Generate a detailed **Impact Report** listing:
  * **Modified Variables**: Old value vs. proposed new value.
  * **Added/Changed Cloud Resources**: Resources affected by the plan.
  * **Safety Guarantee**: Verify that no Spanner instances or active production databases are being destroyed or modified in a destructive manner.
* **Do not run `terraform apply` until the user reviews this Impact Report and gives explicit verbal confirmation (e.g., "Yes", "Approve").**
* Upon approval, execute the deployment:
  ```bash
  terraform apply tfplan.out
  ```

---

## Phase 3: Seed Data Updates & Custom Ingestions

Use this workflow to copy new data files and trigger a new ingestion execution to reload the Spanner database.

### 1. Copy Custom Data to GCS Ingestion Bucket
* Read the target input bucket and input folder from the active configuration.
* Show the user the exact GCS destination path: `gs://[data_bucket_name]/[gcs_data_bucket_input_folder]/`.
* Ask the user for approval to copy the new data files from the local `./data` folder to GCS:
  ```bash
  gcloud storage cp -R ./data/* "gs://${MY_BUCKET}/${INPUT_FOLDER}/"
  ```

### 2. Trigger the Ingestion Pipeline
* **Parameter-free Ingestion Warning**: Explain that the `ingest start` command is completely **parameter-free**. It dynamically resolves variables from Terraform outputs and reads staged configurations directly from GCS.
* **Strict Command Constraint**: **NEVER** append flags like `--import-name` or `--import-list` (handled automatically).
* Present the command and trigger:
  ```bash
  uv run datacommons admin ingest start
  ```
* **Provide Observability Links**: Print both the **Job Console Link** and **Workflow Console Link** in the chat so the user has direct observability.

---

## Phase 4: Operational Monitoring & Health Audits (Gate 2 Verification)

The agent must actively verify that operations complete successfully and that the platform remains highly responsive, keeping the user updated on every step.

### 1. Monitor Ingestion Progress
* Explicitly inform the user you are watching the Cloud Run Job execution logs.
* Output regular status updates (e.g., *"Ingestion job is currently running. Status: Active..."*).
* If errors appear, present the exact error log trace and recommend remediation steps.

### 2. Validate Database Health (Timeout & Sampling Heuristic)
Verify that the ingestion succeeded by querying the Spanner database table **`Observation`** (singular). 

🚨 **Performance Precaution**: Full-table counts (`SELECT COUNT(*)`) can cause expensive full scans and timeouts on large Spanner tables. Follow this safe, observable query flow:

1. **Data Presence Probe**: Tell the user you are running a fast probe to confirm data is active:
   ```bash
   gcloud spanner databases execute-sql [spanner_db_name] \
       --instance=[dcp_spanner_instance_id] \
       --sql="SELECT 1 FROM Observation LIMIT 1"
   ```
2. **Fast Count Scan**: Run a count query:
   ```bash
   gcloud spanner databases execute-sql [spanner_db_name] \
       --instance=[dcp_spanner_instance_id] \
       --sql="SELECT COUNT(1) FROM Observation"
   ```
   * *Query Timeout Handling*: If this query takes more than **15-30 seconds**, abort/cancel the query immediately.
   * *Fall Back to Sampling*: If aborted, report to the user that the table is too large for an immediate full count, and query a small recent sample as proof of successful data load:
     ```bash
     gcloud spanner databases execute-sql [spanner_db_name] \
         --instance=[dcp_spanner_instance_id] \
         --sql="SELECT * FROM Observation LIMIT 10"
     ```
     Present the sample records table directly in the chat.

### 3. Local Health Checks
Establish a background proxy connection to the Cloud Run Website:
```bash
gcloud run services proxy [cloud-run-service-name] --region=us-central1
```
Inform the user and query local port `8080`:
```bash
curl -i -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/healthz
```
Confirm a HTTP `200 OK` response.

---

## Phase 5: Troubleshooting & Diagnosing Common Failures

When components fail, explain the diagnostic path and ask for approval before reading logs:

### 1. Mixer Service Crashes (HTTP 502/503 Errors)
* *Action*: Propose reading the latest 50 lines of Cloud Run service logs:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=[cloud-run-service-name]" --limit=50 --format=json
  ```
* Show logs in the chat, identify Spanner configuration or credentials mismatch errors, and propose fixes.

### 2. Ingestion Job Terminated/Failed
* *Action*: Propose describing the failed Cloud Run job execution:
  ```bash
  gcloud run jobs executions describe [execution_name]
  ```
* Analyze permissions and GCS bucket bindings, and present clear fixes to the user.

---

## Phase 6: Tear-down / Full Clean Wipe

If the partner wishes to completely tear down an environment, guide them safely to avoid data loss.

1. **Backup Alert**: Warn the user to backup any custom Spanner database schemas or GCS input data. **Do not run any destructive commands until they acknowledge.**
2. **Run Terraform Destroy**: Show the exact plan of resources to be destroyed and wait for verbal confirmation before executing:
   ```bash
   terraform destroy
   ```
3. **Erase Remote State**: Ask for permission to delete the Terraform backend state bucket:
   ```bash
   STATE_BUCKET="tf-state-backend-bucket"
   gcloud storage rm --recursive "gs://${STATE_BUCKET}"
   ```
4. **Remove Directories**: Delete generated scaffolding folder:
   ```bash
   rm -rf [namespace_folder]
   ```
5. **Audit Log Update**: Log the wipe out action in the `ops_audit_log.md` file.
