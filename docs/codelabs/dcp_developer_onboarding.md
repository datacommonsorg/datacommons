# Data Commons Platform Developer Onboarding Codelab

## Overview

Welcome to the Data Commons Platform (DCP) developer onboarding codelab. This step-by-step tutorial guides you through setting up, deploying, exploring, and tearing down a fully functional DCP instance on Google Cloud Platform (GCP).

By the end of this codelab, you will understand:
1. The core mental models behind declarative infrastructure (Terraform) and Google Cloud services.
2. How to scaffold and configure a personal DCP deployment using the `datacommons` CLI.
3. How to inspect provisioned resources in the Google Cloud Console.
4. How to seed Cloud Spanner tables, execute a live data ingestion pipeline, and test API endpoints.
5. How to override container images in `terraform.tfvars`, apply updates, and observe rolling Cloud Run revisions.
6. How to safely clean up and tear down cloud resources.

**Target Audience**: Software engineers joining the Data Commons team who have little or no prior experience with Terraform, Cloud Spanner, or GCP.

**Estimated Completion Time**: 45 to 60 minutes.

---

## Prerequisites and Tooling Setup

Before beginning, install and configure the necessary command-line tools on your local machine. For comprehensive workstation setup, virtual environment configuration, and monorepo workflows, refer to the [Developer Guide](../developer_guide.md).

### 1. Install `uv`
`uv` is an extremely fast Python package and tool runner written in Rust. We use it to run the Data Commons CLI without manual virtual environment management.

Install `uv` via the official standalone script:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Verify the installation:
```bash
uv --version
```

### 2. Install HashiCorp Terraform (v1.5+)
Terraform is an Infrastructure as Code (IaC) tool that manages cloud resources declaratively.
* **macOS (Homebrew)**:
  ```bash
  brew tap hashicorp/tap
  brew install hashicorp/tap/terraform
  ```
* **Linux (Debian/Ubuntu)**:
  ```bash
  sudo apt-get update && sudo apt-get install -y gnupg software-properties-common curl
  curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
  sudo apt-get update && sudo apt-get install -y terraform
  ```
Verify the installation:
```bash
terraform version
```

### 3. Install and Authenticate the Google Cloud SDK (`gcloud`)
The `gcloud` CLI authenticates your local terminal to Google Cloud Platform.
1. Install `gcloud` by following the [Google Cloud SDK installation instructions](https://cloud.google.com/sdk/docs/install-sdk).
2. Authenticate your user account:
   ```bash
   gcloud auth login
   ```
3. Authenticate Application Default Credentials (ADC), which allows client libraries and Terraform to authenticate using your Google identity:
   ```bash
   gcloud auth application-default login
   ```
4. Configure your active project (default development project: `datcom-website-dev`):
   ```bash
   gcloud config set project datcom-website-dev
   ```

### 4. Obtain a Data Commons API Key
DCP federates queries to base Google Data Commons. You must supply a valid API key.
1. Visit [apikeys.datacommons.org](https://apikeys.datacommons.org).
2. Sign in with your Google account and generate a free API key.
3. Save this key locally; you will provide it in Step 2.

### 5. Install the Data Commons CLI (`datacommons`)
Install the latest published CLI package from PyPI as a standalone global tool via `uv tool install`:
```bash
# Install the latest published release:
uv tool install datacommons-cli

# Or pin to an exact published release (e.g. 1.1.5):
uv tool install "datacommons-cli==1.1.5"
```
Alternatively, define a shell alias to execute on-the-fly without global installation:
```bash
alias datacommons='uvx --from "datacommons-cli==1.1.5" datacommons'
```

*(If you are developing features inside `packages/datacommons-cli` or `packages/datacommons-admin`, you can execute unreleased code directly from your local monorepo checkout using `uv run --package datacommons-cli datacommons`. See the [Developer Guide](../developer_guide.md#working-on-the-cli-datacommons-cli--datacommons-admin) for details).*

Verify the installation:
```bash
datacommons --version
```

---

## Module 1: The Mental Model (Terraform and GCP 101)

### Declarative vs Imperative
Traditional infrastructure operations are **imperative**: you write bash scripts with explicit sequential steps (`create bucket`, `launch instance`, `install package`). If a step fails halfway through, the environment enters an inconsistent state, and re-running the script often causes collision errors.

Terraform is **declarative**: you write configuration files describing the desired end state of your infrastructure (for example, "I want a Spanner database named `dc-db` and a Cloud Storage bucket named `my-artifacts`").
* When you run `terraform plan`, Terraform compares your declared files against the live state in Google Cloud and computes an execution graph of additions, modifications, and deletions.
* When you run `terraform apply`, Terraform executes only the operations required to make reality match your declaration.

### Persistent vs. Ephemeral GCP Resources
It is critical to distinguish between **persistent foundation infrastructure** and **ephemeral execution workloads**:
* **Persistent Resources (Managed by Terraform)**: Terraform deploys and manages the long-lived, permanent cloud resources that comprise your DCP instance. This includes the Cloud Spanner database, Cloud Storage artifact buckets, Cloud Run serving services and coordination helpers, Secret Manager secrets, and the Cloud Workflows orchestrator. These resources stay alive continuously across ingestions and serve API traffic.
* **Ephemeral Resources (Managed at Runtime by Ingestion)**: In contrast, on-demand compute jobs spawned during data ingestion (such as Dataflow Apache Beam worker clusters and Cloud Run batch worker tasks) are transient. They are dynamically spun up by Cloud Workflows during an ingestion run to execute data processing, stream mutations into Spanner, and shut down upon completion.

Terraform establishes the permanent Google Cloud backbone so that those runtime pipelines and serving microservices have an operational environment to connect to.

### The Resources We Will Provision
When deploying a personal DCP instance, Terraform provisions:
1. **Google Cloud Storage (GCS)**: A storage bucket (`<namespace>-dc-artifacts-<project_id>`) that holds raw CSV/MCF data files, intermediate JSON-LD shards, and pipeline status records.
2. **Google Cloud Spanner**: A distributed, globally consistent relational database. We will create a database (`<namespace>-dc-db`) inside a shared development Spanner instance (`dcp-testing`) to store graph nodes, edges, and observation time series.
3. **Google Cloud Workflows**: A serverless orchestrator (`<namespace>-dc-ingestion-workflow`) that sequences data validation, batch ingestion, and postprocessing.
4. **Google Cloud Run**: Serverless container execution:
   * Serving Service: `datacommons-services` running Envoy, Mixer, and Website.
   * Helper Service: `datacommons-ingestion-helper` managing locks, migration history, and embeddings.
   * Batch Jobs: `datacommons-data` (preprocessor) and `datacommons-aggregation-helper` (postprocessor).
5. **Google Secret Manager**: Secure storage for your Data Commons API key.

---

## Module 2: Scaffolding Your Environment (`datacommons admin init`)

Rather than authoring complex Terraform files by hand, use the `datacommons` CLI to scaffold your deployment.

### 1. Set Your Environment Variables
Choose a unique namespace matching your username or LDAP (for example, `dev-alice`). Keep namespaces lowercase alphanumeric with hyphens, 16 characters or fewer.

```bash
export PROJECT_ID="datcom-website-dev"
export NAMESPACE="dev-yourldap"
export DC_API_KEY="your-api-key-here"
```

### 2. Scaffold the Workspace Directory
Create a directory to hold your local deployment configurations and run `datacommons admin init`:

```bash
mkdir -p ~/dcp-deployments
cd ~/dcp-deployments

datacommons admin init \
    --project-id "$PROJECT_ID" \
    --instance-name "$NAMESPACE" \
    --dc-api-key "$DC_API_KEY"
```

> **Note**: `datacommons admin init` automatically defaults `--tf-git-ref` to the release tag matching your installed CLI package (for example, `v1.1.5`). You do not need to pass `--tf-git-ref` unless you specifically want to target an older release or release candidate.

### 3. Tour the Scaffolded Files
Navigate into your newly generated namespace directory:
```bash
cd ~/dcp-deployments/$NAMESPACE
ls -la
```
You will see five generated files (or four if remote state management was disabled via `--no-tf-remote-state`):
* **`main.tf`**: The root configuration that calls the remote DCP stack module:
  `source = "git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref=v1.1.5"`
* **`variables.tf`**: Variable definitions declaring all configuration options and default values.
* **`outputs.tf`**: Output values that export vital attributes (such as bucket names and service URLs) after deployment.
* **`terraform.tfvars`**: Your instance configuration values.
* **`backend.tf`**: Remote state configuration storing your Terraform state file in a dedicated Cloud Storage bucket (`<project_id>-<instance_name>-tfstate`), ensuring your deployment state is backed up securely in GCP rather than stored only on your local disk.

### 4. Configure `terraform.tfvars` for Shared Development
Open `terraform.tfvars` in your editor. When developing in a shared GCP project (such as `datcom-website-dev`), replace the required placeholders at the top and apply the following cost-saving, quota-safe, and accelerated testing overrides:

```hcl
# ==============================================================================
# REQUIRED USER PLACEHOLDERS (Replace these values first!)
# ==============================================================================
instance_name                                      = "dev-yourldap"       # Replace with your unique namespace (e.g. dev-<ldap>)
auth_google_datacommons_api_key                    = "your-api-key-here"  # Replace with your key from apikeys.datacommons.org
project_id                                         = "datcom-website-dev" # Target Google Cloud project

# ==============================================================================
# Development & Testing Overrides (Pre-configured for shared development)
# ==============================================================================
region                                             = "us-central1"

# Deletion Protection: Keep false for temporary development instances
stateful_deletion_protection                       = false
stateless_deletion_protection                      = false

# Spanner: Reuse shared dev instance to save cost and quota
spanner_create_instance                            = false
spanner_instance_id                                = "dcp-testing"
spanner_create_database                            = true
spanner_create_bigquery_reservation                = false

# Networking & Access
datacommons_services_allow_unauthenticated_access = false
skip_container_restarts                            = true
enable_redis                                       = false

# Ingestion Paths & Dataflow Worker Sizing
ingestion_input_path                               = "ingestion/input"
ingestion_artifacts_path                           = "ingestion/internal"
ingestion_dataflow_num_workers                     = 10
ingestion_dataflow_max_workers                     = 50
ingestion_dataflow_worker_machine_type             = "n2-standard-4"

# Model Context Protocol (MCP) Serving Integration
datacommons_services_enable_mcp                    = true
datacommons_services_mcp_search_scope              = "base_and_custom"
```

---

## Module 3: Deploying Infrastructure (`terraform apply`)

With your configuration in place, deploy the infrastructure.

### 1. Initialize Terraform
Run `terraform init`. This is a **one-time initialization step per deployment workspace** (you only rerun it if you add new provider plugins, reconfigure backend storage, or change module source references).

`terraform init` downloads the Google Cloud provider plugins and clones the remote DCP module specified in `main.tf` into a local `.terraform/` cache:
```bash
terraform init
```
You should see: `Terraform has been successfully initialized!`

> **Architecture Pointer**: During scaffolding, `datacommons admin init` rewrote `source = "./modules/stack"` to point to the remote Git release repository. For details on this regex substitution contract and how the root module orchestrates child modules (`modules/datacommons_services`, `modules/ingestion`, etc.), refer to [Admin CLI Architecture](../architecture/admin_cli.md#the-source-regex-substitution-contract) and [Terraform Stack Architecture](../architecture/terraform_stack.md#orchestration-topology-modulesstack).

### 2. Inspect Execution Plan and Apply
Generate and inspect the execution plan, then apply it to provision your infrastructure.

> **Workflow Note**: Previewing and applying the execution plan (`terraform plan` and `terraform apply`) is the standard workflow you execute **any time you want to modify your GCP resources or configuration** (such as adjusting worker counts, updating image versions, or toggling deletion protection).

Generate and inspect the execution plan:
```bash
terraform plan -out=tfplan
terraform show -no-color tfplan > tfplan.txt
```
Inspect `tfplan.txt` to review the resources being created. Terraform prints a summary at the bottom:
`Plan: ~80 to add, 0 to change, 0 to destroy.`

Now apply the saved execution plan:
```bash
terraform apply tfplan
```

Deployment typically takes 3 to 5 minutes as Google Cloud provisions storage buckets, creates the Spanner database, registers Secret Manager secrets, and deploys Cloud Run services and jobs.

### 3. Capture Outputs
When deployment completes, Terraform displays exported outputs. Export them into your terminal environment for subsequent steps:
```bash
export DATA_BUCKET=$(terraform output -raw storage_artifacts_bucket_name)
export INPUT_PATH=$(terraform output -raw ingestion_input_path)
export ORCHESTRATOR_SA=$(terraform output -raw ingestion_workflow_service_account_email)
export SERVICE_NAME=$(terraform output -raw datacommons_service_name)
export SERVICE_URL=$(terraform output -raw datacommons_service_url)

echo "Data Bucket: gs://$DATA_BUCKET"
echo "Serving URL: $SERVICE_URL"
```

### 4. Grant Service Account Token Impersonation
Grant your user identity permission to impersonate the Cloud Workflows orchestrator service account. This allows you to trigger database seeding and ingestion workflows via the CLI:

```bash
gcloud iam service-accounts add-iam-policy-binding "$ORCHESTRATOR_SA" \
    --member="user:$(gcloud config get-value account)" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --project="$PROJECT_ID"
```

---

## Module 4: The Google Cloud Console Guided Tour

Now open the Google Cloud Console in your browser:
```
https://console.cloud.google.com/?project=<PROJECT_ID>
```
*(If you are deploying to the shared development project, this is `https://console.cloud.google.com/?project=datcom-website-dev`). Verify that the project dropdown in the top console navigation bar matches your `$PROJECT_ID`.*

### 1. Cloud Storage
* In the search bar at the top, type `Cloud Storage` and select **Buckets**.
* Locate your bucket: `<namespace>-dc-artifacts-<project_id>`.
* Click into the bucket. Notice that Terraform created the folder structure:
  * `ingestion/input/`: Where raw data files will be uploaded.
  * `ingestion/metadata/`: Where pipeline execution logs, import versions, and handshakes are tracked.

### 2. Cloud Spanner
* In the search bar, type `Spanner` and select **Instances**.
* Click into your Spanner instance (if using the shared dev overrides from Module 2, this is `dcp-testing`, or your custom instance name if you configured a dedicated instance).
* Under the **Databases** tab, locate your database: `<namespace>-dc-db`.
* Click into your database and select **Spanner Studio** on the left menu.
* Notice that the database currently has zero tables. The database exists, but schemas have not yet been applied. We will apply them in Module 5.

### 3. Cloud Run (Services and Jobs)
* In the search bar, type `Cloud Run` and view both tabs:
  * **Services**: Locate `<namespace>-dc-datacommons-service` (the Envoy, Mixer, and Website serving container) and `<namespace>-dc-ingestion-helper` (the coordination microservice). Click into `datacommons-service` to inspect CPU, memory, and logs.
  * **Jobs**: Click the **Jobs** tab at the top. Locate `<namespace>-dc-prep-job` and `<namespace>-dc-post-job`. Cloud Run Jobs differ from Services: Services listen continuously for HTTP traffic, while Jobs run batch tasks to completion and terminate.

### 4. Cloud Workflows
* In the search bar, type `Workflows` and select **Workflows**.
* Locate `<namespace>-dc-ingestion-workflow`.
* Click into the workflow and view the **Source** tab. Notice how the workflow definition matches `infra/dcp/modules/ingestion/workflow/workflow.yaml`.

### 5. Artifact Registry and Container Registry
* In the search bar, type `Artifact Registry` and select **Repositories**.
* Locate `datacommons-artifacts` in `us-central1`. This repository stores custom container images for ingestion (`datacommons-data` and `ingestion-helper`).
* Also search for `Container Registry` to view `gcr.io/datcom-website-dev/datacommons-services` (the serving container) and `datacommons-aggregation-helper`.
* Notice the image tags published here (such as `latest`, `v1.1.2`, `v1.1.3`, and developer test tags). This is the registry where Cloud Run and Cloud Workflows fetch container images during deployment and workflow execution.

---

## Module 5: Database Seeding and Schema Initialization

Now initialize the Spanner schema and seed base statistical metadata using the CLI.

### 1. Run `datacommons admin init-db`
Make sure you are in your deployment directory (`~/dcp-deployments/$NAMESPACE`) and run:

```bash
datacommons admin init-db
```

The CLI executes the following sequence:
1. Reads Spanner outputs and the ingestion helper URL from your local Terraform state.
2. Authenticates against the ingestion helper service using OIDC token impersonation.
3. Applies base DDL scripts to create Spanner tables (`Node`, `Edge`, `Observation`, `TimeSeries`, `ImportStatus`, `IngestionHistory`).
4. Runs pending [schema migration scripts](../schema_migrations_developer_guide.md).
5. Seeds base metadata nodes (statistical variables, units, and sources).

### 2. Verify Tables in Spanner Studio
Return to the Google Cloud Console, navigate to **Spanner > `<spanner_instance_id>` (e.g. `dcp-testing`) > `<namespace>-dc-db` > Spanner Studio**, and run the following queries:

```sql
-- Check that schema tables exist
SELECT table_name FROM information_schema.tables WHERE table_schema = '';
```
You will see tables including `Node`, `Edge`, `Observation`, `TimeSeries`, and `IngestionHistory`.

```sql
-- Inspect initial seeded metadata nodes
SELECT subject_id, predicate, object_value FROM Node LIMIT 10;
```

---

## Module 6: Ingesting Your First Dataset

Next, stage a sample dataset in Cloud Storage and execute the ingestion workflow.

### 1. Stage Committed Test Datasets in Cloud Storage
Copy the committed integration test datasets from your local repository clone into your deployment's input bucket:

```bash
# Run from the root of your datcom-datacommons clone:
gcloud storage cp -r tests/integration/test_data/* "gs://$DATA_BUCKET/$INPUT_PATH/"
```

Verify that the files exist in GCS:
```bash
gcloud storage ls "gs://$DATA_BUCKET/$INPUT_PATH/"
```
The bucket contains committed test dataset folders (`foobar_wages`, `foobar_education`, `financial_trade`). Each dataset contains CSV observations, schema MCFs, and `config.json` mappings.

### 2. Start Ingestion via the CLI
Trigger the ingestion workflow. You can ingest a single dataset (`foobar_wages`) or multiple datasets concurrently:

```bash
# Ingest single dataset:
datacommons admin ingest start --imports foobar_wages

# Or ingest multiple datasets concurrently:
datacommons admin ingest start \
    --imports="foobar_wages,foobar_education,financial_trade"
```

The CLI prints the execution ID and a direct URL to Google Cloud Console:
```
Execution ID: <execution-id>
Execution console link: https://console.cloud.google.com/workflows/workflow/us-central1/...
```

### 3. Monitor Execution and View Logs in the Cloud Console
Click the console link printed in your terminal or open **Workflows > `<namespace>-dc-ingestion-workflow` > Executions**.
Watch the workflow progress through its stages, and inspect the underlying compute jobs and logs in real time:

1. **`run_preprocessing`**: Launches Cloud Run job `datacommons-data` to validate `config.json` and generate JSON-LD chunks.
   * *Viewing Job Logs*: Open **Cloud Run > Jobs** in the console, click into `<namespace>-dc-prep-job`, click the active execution, and select the **Logs** tab to view schema validation and record sharding output.
2. **`try_acquire_lock`**: Contacts `datacommons-ingestion-helper` to acquire the database lock in Spanner.
3. **`launch_dataflow`**: Launches the Apache Beam Dataflow job (`GraphIngestionPipeline`) to load nodes, edges, and observations into Spanner.
   * *Viewing Dataflow Graph and Logs*: Open **Dataflow > Jobs** in the console and click into the running job (named `graph-ingestion-pipeline-...`). You can view the live execution DAG (stages such as `ReadJSONLD`, `ExtractFacets`, and `WriteToSpanner`). Click the **Job Logs** tab for pipeline lifecycle events and the **Worker Logs** tab to stream real-time worker output.
4. **`run_postprocessing_parallel`**: Runs BigQuery federated queries to materialize statistical variable groups and invokes Vertex AI text embeddings.
   * *Viewing Postprocessing Logs*: Open **Cloud Run > Jobs**, click into `<namespace>-dc-post-job`, click the active execution, and select the **Logs** tab to observe BigQuery aggregation and vector embedding generation.
5. **`release_lock_step` & `restart_service`**: Releases the Spanner lock and triggers a rolling container restart of `datacommons-services` so the new data is served immediately.

Ingestion typically takes 4 to 6 minutes. Wait until the execution status displays a green checkmark (`Succeeded`).

---

## Module 7: Verifying the Serving Stack and Running Integration Tests

Now verify that your instance serves the newly ingested statistical observations and practice running automated integration tests.

### 1. Establish a Local Proxy Tunnel
By default, Cloud Run services in development environments require authenticated IAM tokens. Establish a local proxy tunnel to forward authenticated requests:

In a **separate terminal window**, run:
```bash
gcloud run services proxy "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="us-central1" \
    --port=8080
```
Keep this terminal running. The proxy listens on `http://localhost:8080` and automatically injects authentication headers.

### 2. Test Observation API Queries
In your original terminal, submit a curl request to query observations for average annual wage:

```bash
curl -s -g -H "X-Use-Multi-Entity-Schema: true" \
  "http://localhost:8080/core/api/v2/observation?select=variable&select=entity&select=date&select=value&variable.dcids=average_annual_wage&entity.dcids=country/USA" | jq .
```
You will see JSON observations containing dates, wage values, and provenance metadata returned from your private Spanner database.

### 3. Test Natural Language Entity and Indicator Resolution
Test the entity resolution endpoint to verify that Vertex AI text embeddings are functioning for custom indicators:

```bash
# Query custom wages indicator:
curl -s -g "http://localhost:8080/core/api/v2/resolve?nodes=wages&resolver=indicator&target=custom_only" | jq .

# Query gender wage gap indicator:
curl -s -g "http://localhost:8080/core/api/v2/resolve?nodes=gender%20wage%20gap&resolver=indicator&target=custom_only" | jq .
```
The response resolves natural language queries to custom statistical variables and topics (such as `average_annual_wage` and `gender_wage_gap`).

### 4. Inspect the Web Interface
Open your web browser and navigate to:
```
http://localhost:8080
```
Browse the homepage, use the search bar to look for "wages", and view the generated charts.

### 5. Run the Automated Integration Test Suite
Now that your instance is live and populated with `foobar_wages`, practice executing the repository's automated integration test suite against your personal deployment.

From the root of your `datcom-datacommons` repository clone, execute:
```bash
uv run python tests/integration/run_e2e_tests.py \
    --project "$PROJECT_ID" \
    --instance "$NAMESPACE" \
    --test-config foobar_wages \
    --reuse-data
```

Because you already ingested `foobar_wages` in Module 6, passing `--reuse-data` skips repeating the 5-minute ingestion pipeline and immediately runs the validation suites (`02_postprocessing`, `03_serving_api`, and `04_mcp_agent`) against your live deployment.

To test a specific stage (for example, only the serving API tests):
```bash
uv run python tests/integration/run_e2e_tests.py \
    --project "$PROJECT_ID" \
    --instance "$NAMESPACE" \
    --test-config foobar_wages \
    --suite 03_serving_api \
    --reuse-data
```

For advanced testing options, including running the entire stack hermetically in local Docker emulators without GCP infrastructure, refer to the [Integration Test Suite Guide](../../tests/integration/README.md).

---

## Module 8: Overriding Container Images and Applying Configuration Changes

A common task during DCP development is modifying instance settings or pointing your instance to a custom-built container image (for example, testing a new feature in Website or Mixer).

In this module, you will practice the day-to-day workflow of modifying `terraform.tfvars`, generating an execution plan, applying the change, and observing the rolling update in the Google Cloud Console.

### 1. Inspect the Active Revision in Cloud Run
Return to the Google Cloud Console and navigate to **Cloud Run > Services > `<namespace>-dc-datacommons-service`**.
* Click the **Revisions** tab.
* Note the container image URL currently serving 100% of traffic (for example, `gcr.io/datcom-website-dev/datacommons-services:latest` or `v1.1.5`).

### 2. Override the Container Image in `terraform.tfvars`
Open `~/dcp-deployments/$NAMESPACE/terraform.tfvars` in your editor.
At the bottom of the file, add an override for the serving container pointing to a specific prior release tag (such as `v1.1.3`):

```hcl
# Override serving container image to a specific release tag:
datacommons_services_image = "gcr.io/datcom-website-dev/datacommons-services:v1.1.3"
```

Save the file.

### 3. Generate and Inspect the Execution Plan
Generate an updated execution plan:

```bash
terraform plan -out=tfplan
terraform show -no-color tfplan > tfplan.txt
```

Open `tfplan.txt` and review the output.
Notice the summary at the bottom:
```
Plan: 0 to add, 1 to change, 0 to destroy.
```

Observe how declarative infrastructure operates: Terraform compares your modified configuration against the live GCP environment, recognizes that only the Cloud Run container image has changed, and prepares an in-place update without touching or recreating your Spanner database, storage buckets, or IAM bindings.

### 4. Apply the Update
Apply the saved plan:

```bash
terraform apply tfplan
```

Deployment takes roughly 30 to 45 seconds. Terraform updates the Cloud Run service definition, and Cloud Run provisions a new container revision with zero downtime.

### 5. Verify the New Revision in Google Cloud Console
Return to **Cloud Run > Services > `<namespace>-dc-datacommons-service`** in the Google Cloud Console and refresh the **Revisions** tab:
1. You will see a new revision listed at the top (for example, `<namespace>-dc-datacommons-service-00002-...`).
2. Verify that the **Container image URL** displays `gcr.io/datcom-website-dev/datacommons-services:v1.1.3`.
3. Notice that Cloud Run automatically routed 100% of traffic to this new revision.

> **Building Your Own Custom Images**: To learn how to build your own custom container images from `datcom-website` or `datcom-import` and push them to Artifact Registry using `gcloud builds submit`, refer to [Building and Overriding Container Images in the Developer Guide](../developer_guide.md#working-with-container-images-building--overriding).

---

## Module 9: Safe Teardown and Resource Cleanup

When you complete your testing, clean up your resources to avoid unnecessary cloud costs and release quotas.

> [!WARNING]
> **Data Loss Warning**: This procedure permanently destroys all cloud resources created for your DCP instance, including your Cloud Spanner database, Cloud Run services, Secret Manager secrets, and Cloud Storage buckets. If there is any data in your provisioned GCS buckets that you wish to keep, copy it to an external location before proceeding.

### 1. Understanding Deletion Protection
DCP incorporates deletion protection to guard against accidental data loss. In `terraform.tfvars`, two variables govern protection:
* `stateful_deletion_protection`: Guards Spanner databases, instances, and GCS storage buckets.
* `stateless_deletion_protection`: Guards Cloud Run services, jobs, and Cloud Workflows.

If you attempt to run `terraform destroy` while `stateful_deletion_protection = true`, Terraform aborts with an error preventing destruction.

### 2. Update Configuration for Teardown
To cleanly tear down your temporary development instance, ensure both protection variables are set to `false` in `terraform.tfvars`:
```hcl
stateful_deletion_protection  = false
stateless_deletion_protection = false
```

Apply the updated protection settings:
```bash
terraform apply -auto-approve
```

### 3. Destroy Provisioned GCP Resources
Navigate to your deployment folder and execute `terraform destroy`:

```bash
cd ~/dcp-deployments/$NAMESPACE
terraform destroy
```

Terraform presents the deletion plan:
`Plan: 0 to add, 0 to change, ~80 to destroy.`

Type `yes` and press Enter. Once complete, Terraform confirms:
`Destroy complete! Resources: ~80 destroyed.`

Because you configured `spanner_create_instance = false`, Terraform deletes your private database (`<namespace>-dc-db`) while preserving the shared `dcp-testing` Spanner instance for teammates.

### 4. Clean Up Remote State Bucket and Local Files
Because `backend.tf` stores Terraform state in a dedicated Cloud Storage bucket, `terraform destroy` deletes the resources declared within your stack but intentionally leaves the remote state bucket and your local configuration folder intact.

To complete a full wipe:
1. Inspect `backend.tf` to identify your remote state bucket name:
   ```bash
   cat backend.tf
   ```
2. Delete the remote state bucket and all stored state files:
   ```bash
   STATE_BUCKET=$(grep -o 'bucket = "[^"]*"' backend.tf | cut -d'"' -f2)
   gcloud storage rm --recursive "gs://$STATE_BUCKET"
   ```
3. Remove your local deployment folder:
   ```bash
   cd ..
   rm -rf "$NAMESPACE"
   ```

### 5. Troubleshooting: Lost Your Local Terraform State Folder?
If you accidentally deleted your local workspace folder, or ran inside an ephemeral Docker container:
1. Re-run `datacommons admin init` with the **same** `--project-id` and `--instance-name` to re-scaffold the directory and reconnect to your remote state bucket.
2. Inside the recreated folder, run `terraform init -reconfigure` to reconnect to the state bucket, then execute `terraform destroy`.

---

## Conclusion and Next Steps

Congratulations! You have successfully scaffolded, deployed, explored, verified, and torn down a Data Commons Platform instance.

### Recommended Next Reads
* **[Platform Architecture and Data Flows](../architecture/platform_architecture.md)**: Explore the 4-repository layout and end-to-end data flows in greater depth.
* **[Terraform Stack Architecture](../architecture/terraform_stack.md)**: Learn how Terraform submodules, variable propagation, and cross-module IAM policies are structured.
* **[Admin CLI Architecture](../architecture/admin_cli.md)**: Study how the CLI interacts with local and remote Terraform state.
* **[Developer Guide to Schema Migrations](../schema_migrations_developer_guide.md)**: Learn how to author and test Spanner DDL migration scripts.
