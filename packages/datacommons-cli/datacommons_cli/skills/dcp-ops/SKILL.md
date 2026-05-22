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
> * **GCP Console Deep-Links**: Whenever a resource is created or modified, the agent must construct and print the direct Google Cloud Console deep-links (e.g. GCS browser, Spanner console, Cloud Run dashboard) to enable instant user verification and audit.
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
* Explain that we are about to trigger the Cloud Run Ingestion Job, show the command, and ask for permission to execute:
  ```bash
  uv run datacommons admin ingest start
  ```
* **Provide Ingestion Logs Link**: Once executed, capture the **Job Console Link** from the logs and present it clearly in the chat so the user has direct observability in their browser console.

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
