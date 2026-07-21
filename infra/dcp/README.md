# Data Commons Platform (DCP) Infrastructure Guide

This directory contains the Terraform configuration to deploy the Data Commons Platform on Google Cloud Platform (GCP). This guide will walk you through setting up the infrastructure and running your first data ingestion workflow.

## Prerequisites

Before you begin, ensure you have the following:

*   **GCP Project**: A Google Cloud project with billing enabled.
*   **Terraform**: Installed locally (version >= 1.0.0).
*   **gcloud CLI**: Installed and authenticated to your GCP project.
    ```bash
    gcloud auth login
    gcloud config set project <your-project-id>
    ```
*   **Permissions**: Ensure your user or service account has sufficient permissions to create Spanner databases, Cloud Run services, IAM bindings, and GCS buckets.

## Initial Setup

### Remote Module Quick Start (Minimal Consumer Config)

If you want users to deploy from this module remotely (without cloning this repo), start from:

*   [examples/remote-module/main.tf](examples/remote-module/main.tf)
*   [examples/remote-module/terraform.tfvars.template](examples/remote-module/terraform.tfvars.template)

This uses a Git module source in the form:

```hcl
source = "git::https://github.com/<org>/<repo>.git//infra/dcp?ref=<tag-or-commit>"
```

Use a release tag or commit SHA (instead of `main`) for reproducible environments.

### 1. Configure Local Variables

Copy the example variables file to create your local configuration:
```bash
cp terraform.tfvars.template terraform.tfvars
```

Edit `terraform.tfvars` and fill in at least the following required variables:
*   `project_id`: Your GCP Project ID.
*   `instance_name`: A unique identifier for resource naming (e.g., your name or team name).

### 2. Run the Setup Script

The `setup.sh` script automates the creation of a GCS bucket for storing Terraform state and initializes the backend configuration.
```bash
./setup.sh
```
This script will also enable necessary Google Cloud APIs for your project.

## Configuration Guide (`terraform.tfvars`)

You can control the deployment by setting values in `terraform.tfvars`. Here are the key configurations:

### Stack Toggles
*   `enable_datacommons_service` (bool): Set to `true` to deploy the main Data Commons service. Defaults to `true`.
*   `enable_platform_service` (bool): Set to `true` to deploy the platform service. Defaults to `true`.

### Data Ingestion Config
*   `deploy_ingestion_workflow` (bool): Set to `true` to deploy the Cloud Workflows orchestrator and ingestion runner service account.
*   `ingestion_service_image` (string): Docker image URL for the ingestion support service.
*   `ingestion_prep_job_image` (string): Docker image URL for the data ingestion pre-processing job.
*   `ingestion_prep_bucket_input_folder` (string): GCS data bucket input folder for pre-processing. Defaults to `input`.
*   `create_ingestion_bucket` (bool): Controls whether Terraform automatically provisions a dedicated staging GCS bucket for uploading graph dataset (.mcf) files. Defaults to `true`.
*   `ingestion_bucket_name` (string): The name of the ingestion bucket (used for creation if `create_ingestion_bucket` is true, or as the existing bucket name if false).

### Access Control
*   `allow_unauthenticated_access` (bool): Controls whether Cloud Run services are publicly accessible (unauthenticated). Defaults to `false` for security.

## Deployment

Once configured, execute standard Terraform commands to provision resources:

1.  **Initialize**:
    ```bash
    terraform init
    ```
2.  **Plan**:
    ```bash
    terraform plan
    ```
3.  **Apply**:
    ```bash
    terraform apply
    ```

## Outputs

Upon successful apply, Terraform displays key endpoints and resource names:
*   `platform_service_url`: Cloud Run service URL for the platform service.
*   `datacommons_service_url`: Cloud Run service URL for the Data Commons service.
*   `ingestion_workflow_name`: Name of the Cloud Workflows ingestion orchestrator.
*   `ingestion_service_uri`: URI of the ingestion support Cloud Run service.
*   `ingestion_prep_job_name`: Name of the data ingestion pre-processing job.
*   `spanner_instance_id`: ID of the provisioned or referenced Cloud Spanner instance.
*   `spanner_database_id`: ID of the provisioned Cloud Spanner database.

## Running Data Ingestion Workflow

After successful deployment with `deploy_ingestion_workflow = true`, you can run the automated ingestion pipeline.

### Step 1: Upload your Schema file
Upload your custom graph nodes file (`.mcf`) to the provisioned ingestion bucket. By default, the bucket name format is: `<instance-name>-ingestion-bucket-<project_id>`.

```bash
gcloud storage cp path/to/your/sample.mcf gs://<instance-name>-ingestion-bucket-<project_id>/imports/sample.mcf
```

### Step 2: Trigger the Workflow Orchestrator
Trigger the Cloud Workflow to start the Dataflow job that will read the file and insert it into Spanner.

```bash
gcloud workflows run <instance-name>-ingestion-orchestrator \
  --project=<project_id> \
  --location=<region> \
  --data='{
    "templateLocation": "gs://datcom-templates/templates/flex/ingestion.json",
    "region": "<region>",
    "spannerInstanceId": "<spanner-instance-id>",
    "spannerDatabaseId": "<spanner-database-id>",
    "importList": "[{\"importName\": \"SampleTestCase\", \"graphPath\": \"gs://<instance-name>-ingestion-bucket-<project_id>/imports/sample.mcf\"}]",
    "tempLocation": "gs://<instance-name>-ingestion-bucket-<project_id>/temp"
  }'
```

**Key Data Parameters:**
*   `spannerInstanceId`: The ID of your Spanner instance.
*   `spannerDatabaseId`: The ID of your Spanner database.
*   `importList`: A JSON string mapping the import logical name to the GCS path of the MCF file.

### Step 3: (Alternative) Trigger via CLI

If you are using the `datacommons` CLI, you can trigger the ingestion job more easily without constructing the JSON payload:

```bash
uv run datacommons admin ingest start --imports <import1>[,<import2>]
```

This will use the `import_name` to find the corresponding configuration in your bucket and trigger the workflow.

### Modular Structure
Stack composition is delegated to `modules/stack`, which manages smaller, dedicated sub-modules for various components of the Data Commons Platform.

### Module Overview
*   **`stack`**: Orchestrates sub-modules ([modules/stack](modules/stack/main.tf)).
*   **`ingestion_prep_job`**: Ingestion Cloud Run v2 Job for pre-processing.
*   **`iam`**: IAM and Secret Manager config.
*   **`networking`**: VPC and serverless access connectors.
*   **`redis`**: Memorystore Redis instance.
*   **`datacommons_service`**: Main Data Commons Cloud Run v2 web service.
*   **`ingestion_dataflow`**: Dataflow runner service account and IAM ([modules/ingestion_dataflow](modules/ingestion_dataflow/main.tf)).
*   **`ingestion_service`**: Helper Cloud Run service for ingestion ([modules/ingestion_service](modules/ingestion_service/main.tf)).
*   **`ingestion_workflow`**: Cloud Workflows for orchestration.
*   **`platform_service`**: Platform service Cloud Run service.
*   **`storage`**: GCS buckets ([modules/storage](modules/storage/main.tf)).
*   **`spanner`**: Shared Cloud Spanner instance and databases.

### Orchestrator Pattern
The ingestion pipeline uses Google Cloud Workflows as an orchestrator. It receives the ingestion parameters, names the Dataflow job with a timestamp, launches the Dataflow Flex Template, and returns the job status. This prevents direct interaction with complex Dataflow APIs for standard ingestion tasks.

### Troubleshooting: Deletion Protection
If you encounter errors destroying resources (like Spanner databases or GCS buckets), ensure you have set `deletion_protection = false` in your variables if you intended to destroy them. By default, deletion protection is enabled to prevent accidental data loss.
