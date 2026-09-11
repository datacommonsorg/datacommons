# Data Commons Platform Developer Onboarding Codelab

## Overview

Welcome to the Data Commons Platform (DCP) developer onboarding codelab. This step-by-step tutorial guides you through setting up, deploying, exploring, and tearing down a fully functional DCP instance on Google Cloud Platform (GCP).

By the end of this codelab, you will understand:
1. The core mental models behind declarative infrastructure (Terraform) and Google Cloud services.
2. How to scaffold and configure a personal DCP deployment using the `datacommons` CLI.
3. How to inspect provisioned resources in the Google Cloud Console.
4. How to seed Cloud Spanner tables, execute a live data ingestion pipeline, and test API endpoints.
5. How to safely clean up and tear down cloud resources.

**Target Audience**: Software engineers joining the Data Commons team who have little or no prior experience with Terraform, Cloud Spanner, or GCP.

**Estimated Completion Time**: 45 to 60 minutes.

---

## Prerequisites and Tooling Setup

Before beginning, install and configure the necessary command-line tools on your local machine.

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

---

## Module 1: The Mental Model (Terraform and GCP 101)

### Declarative vs Imperative
Traditional infrastructure operations are **imperative**: you write bash scripts with explicit sequential steps (`create bucket`, `launch instance`, `install package`). If a step fails halfway through, the environment enters an inconsistent state, and re-running the script often causes collision errors.

Terraform is **declarative**: you write configuration files describing the desired end state of your infrastructure (for example, "I want a Spanner database named `dc-db` and a Cloud Storage bucket named `my-artifacts`").
* When you run `terraform plan`, Terraform compares your declared files against the live state in Google Cloud and computes a execution graph of additions, modifications, and deletions.
* When you run `terraform apply`, Terraform executes only the operations required to make reality match your declaration.

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

uvx --no-cache --from "git+https://github.com/datacommonsorg/datacommons.git@main#subdirectory=packages/datacommons-cli" \
    datacommons admin init \
    --project-id "$PROJECT_ID" \
    --namespace "$NAMESPACE" \
    --dc-api-key "$DC_API_KEY" \
    --tf-git-ref main
```

### 3. Tour the Scaffolded Files
Navigate into your newly generated namespace directory:
```bash
cd ~/dcp-deployments/$NAMESPACE
ls -la
```
You will see four generated files:
* **`main.tf`**: The root configuration that calls the remote DCP stack module:
  `source = "git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref=main"`
* **`variables.tf`**: Variable definitions declaring all configuration options and default values.
* **`outputs.tf`**: Output values that export vital attributes (such as bucket names and service URLs) after deployment.
* **`terraform.tfvars`**: Your instance configuration values.

### 4. Configure `terraform.tfvars` for Shared Development
Open `terraform.tfvars` in your editor. When developing in a shared GCP project (such as `datcom-website-dev`), apply the following cost-saving and quota-safe overrides:

```hcl
# GCP Project and Identity
project_id = "datcom-website-dev"
namespace  = "dev-yourldap"
region     = "us-central1"

# DCP Stack Authentication
auth_google_datacommons_api_key = "your-api-key-here"
dcp_version                     = "latest"
enable_redis                    = false

# Ingestion Paths
ingestion_input_path = "ingestion/input"

# Cloud Spanner: Reuse shared dev instance to save cost and quota
spanner_create_instance = false
spanner_instance_id     = "dcp-testing"
spanner_create_database = true

# BigQuery Reservation: Set to false to avoid quota collisions in shared projects
spanner_create_bigquery_reservation = false

# Deletion Protection: Keep false for temporary development instances
stateful_deletion_protection  = false
stateless_deletion_protection = false
```

---

## Module 3: Deploying Infrastructure (`terraform apply`)

With your configuration in place, deploy the infrastructure.

### 1. Initialize Terraform
`terraform init` downloads the Google Cloud provider plugins and clones the remote DCP module specified in `main.tf`:
```bash
terraform init
```
You should see: `Terraform has been successfully initialized!`

### 2. Preview the Execution Plan
Run `terraform plan` to view the exact changes Terraform intends to perform without applying them:
```bash
terraform plan
```
Terraform prints a summary at the bottom:
`Plan: ~25 to add, 0 to change, 0 to destroy.`

### 3. Apply the Configuration
Execute the deployment:
```bash
terraform apply
```
Terraform displays the proposed plan again and prompts for confirmation. Type `yes` and press Enter.

Deployment typically takes 3 to 5 minutes as Google Cloud provisions storage buckets, creates the Spanner database, and registers Cloud Run containers.

### 4. Capture Outputs
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

### 5. Grant Service Account Token Impersonation
Grant your user identity permission to impersonate the Cloud Workflows orchestrator service account. This allows you to trigger database seeding and ingestion workflows via the CLI:

```bash
gcloud iam service-accounts add-iam-policy-binding "$ORCHESTRATOR_SA" \
    --member="user:$(gcloud config get-value account)" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --project="$PROJECT_ID"
```

---

## Module 4: The Google Cloud Console Guided Tour

Now open the [Google Cloud Console](https://console.cloud.google.com/?project=datcom-website-dev) in your browser and tour the resources Terraform created.

### 1. Cloud Storage
* In the search bar at the top, type `Cloud Storage` and select **Buckets**.
* Locate your bucket: `<namespace>-dc-artifacts-datcom-website-dev`.
* Click into the bucket. Notice that Terraform created the folder structure:
  * `ingestion/input/`: Where raw data files will be uploaded.
  * `ingestion/metadata/`: Where pipeline execution logs, import versions, and handshakes are tracked.

### 2. Cloud Spanner
* In the search bar, type `Spanner` and select **Instances**.
* Click into the `dcp-testing` instance.
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

---

## Module 5: Database Seeding and Schema Initialization

Now initialize the Spanner schema and seed base statistical metadata using the CLI.

### 1. Run `datacommons admin init-db`
Make sure you are in your deployment directory (`~/dcp-deployments/$NAMESPACE`) and run:

```bash
uvx --no-cache --from "git+https://github.com/datacommonsorg/datacommons.git@main#subdirectory=packages/datacommons-cli" \
    datacommons admin init-db
```

The CLI executes the following sequence:
1. Reads Spanner outputs and the ingestion helper URL from your local Terraform state.
2. Authenticates against the ingestion helper service using OIDC token impersonation.
3. Applies base DDL scripts to create Spanner tables (`Node`, `Edge`, `Observation`, `TimeSeries`, `ImportStatus`, `IngestionHistory`).
4. Runs pending schema migration scripts from `packages/datacommons-db/migration_scripts/`.
5. Seeds base metadata nodes (statistical variables, units, and sources).

### 2. Verify Tables in Spanner Studio
Return to the Google Cloud Console, navigate to **Spanner > dcp-testing > `<namespace>-dc-db` > Spanner Studio**, and run the following queries:

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

### 1. Stage Sample Test Data in Cloud Storage
Copy the pre-configured sample frog dataset into your deployment's input bucket:

```bash
gcloud storage cp -R gs://datcom-website-dev-calinc/dcp-test-data/frog_data/* "gs://$DATA_BUCKET/$INPUT_PATH/frog_data/"
```

Verify that the files exist in GCS:
```bash
gcloud storage ls "gs://$DATA_BUCKET/$INPUT_PATH/frog_data/"
```
The folder contains three files:
* `frog_observations.csv`: Statistical observations of frog populations.
* `frog_schema.mcf`: Graph schema defining the frog species entities and statistical variables.
* `config.json`: Column mapping instructions telling the preprocessor how to parse the CSV columns into Data Commons identifiers.

### 2. Start Ingestion via the CLI
Trigger the ingestion workflow for the `frog_data` dataset:

```bash
uvx --no-cache --from "git+https://github.com/datacommonsorg/datacommons.git@main#subdirectory=packages/datacommons-cli" \
    datacommons admin ingest start --imports frog_data
```

The CLI prints the execution ID and a direct URL to Google Cloud Console:
```
Execution ID: <execution-id>
Execution console link: https://console.cloud.google.com/workflows/workflow/us-central1/...
```

### 3. Monitor Execution in the Cloud Console
Click the console link printed in your terminal or open **Workflows > `<namespace>-dc-ingestion-workflow` > Executions**.
Watch the workflow progress through its stages:
1. **`run_preprocessing`**: Launches the `datacommons-data` Cloud Run job to validate `config.json` and generate JSON-LD chunks.
2. **`try_acquire_lock`**: Contacts `datacommons-ingestion-helper` to lock the Spanner database.
3. **`launch_dataflow`**: Launches the Apache Beam Dataflow job (`GraphIngestionPipeline`) to load nodes, edges, and observations into Spanner.
4. **`run_postprocessing_parallel`**: Runs BigQuery federated queries to materialize statistical variable groups and invokes Vertex AI text embeddings.
5. **`release_lock_step` & `restart_service`**: Unlocks Spanner and triggers a rolling container restart of `datacommons-services` so the new data is served immediately.

Ingestion typically takes 4 to 6 minutes. Wait until the execution status displays a green checkmark (`Succeeded`).

---

## Module 7: Verifying the Serving Stack

Now verify that your instance serves the newly ingested frog observations.

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
In your original terminal, submit a curl request to query observations for frog population:

```bash
curl -s -g -H "X-Use-Multi-Entity-Schema: true" \
  "http://localhost:8080/core/api/v2/observation?select=variable&select=entity&select=date&select=value&variable.dcids=Count_Frog&entity.dcids=country/USA" | jq .
```
You will see JSON observations containing dates, values, and provenance metadata returned from your private Spanner database.

### 3. Test Natural Language Entity Resolution
Test the entity resolution endpoint to verify that Vertex AI text embeddings are functioning:

```bash
curl -s -g "http://localhost:8080/core/api/v2/resolve?nodes=frog%20population&resolver=indicator&target=custom_only" | jq .
```
The response resolves the query `frog population` to the custom statistical variable `Count_Frog`.

### 4. Inspect the Web Interface
Open your web browser and navigate to:
```
http://localhost:8080
```
Browse the homepage, use the search bar to look for "frog", and view the generated charts.

---

## Module 8: Safe Teardown and Resource Cleanup

When you complete your testing, clean up your resources to avoid unnecessary cloud costs.

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

### 3. Destroy Provisioned Resources
Execute `terraform destroy` to delete all provisioned resources:

```bash
terraform destroy
```

Terraform presents the deletion plan:
`Plan: 0 to add, 0 to change, ~25 to destroy.`

Type `yes` and press Enter. Once complete, Terraform confirms:
`Destroy complete! Resources: 25 destroyed.`

Because you configured `spanner_create_instance = false`, Terraform deletes your private database (`<namespace>-dc-db`) while preserving the shared `dcp-testing` Spanner instance for teammates.

---

## Conclusion and Next Steps

Congratulations! You have successfully scaffolded, deployed, explored, verified, and torn down a Data Commons Platform instance.

### Recommended Next Reads
* **[Platform Architecture and Data Flows](../architecture/platform_architecture.md)**: Explore the 4-repository layout and end-to-end data flows in greater depth.
* **[Terraform Stack Architecture](../architecture/terraform_stack.md)**: Learn how Terraform submodules, variable propagation, and cross-module IAM policies are structured.
* **[Admin CLI Architecture](../architecture/admin_cli.md)**: Study how the CLI interacts with local and remote Terraform state.
* **[Developer Guide to Schema Migrations](../schema_migrations_developer_guide.md)**: Learn how to author and test Spanner DDL migration scripts.
