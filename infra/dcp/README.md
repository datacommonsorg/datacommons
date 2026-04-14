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

### 1. Configure Local Variables

Copy the example variables file to create your local configuration:
```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and fill in at least the following required variables:
*   `project_id`: Your GCP Project ID.
*   `namespace`: A unique identifier for resource naming (e.g., your name or team name).

### 2. Run the Setup Script

The `setup.sh` script automates the creation of a GCS bucket for storing Terraform state and initializes the backend configuration.
```bash
./setup.sh
```
This script will also enable necessary Google Cloud APIs for your project.

## Configuration Guide (`terraform.tfvars`)

You can control the deployment by setting values in `terraform.tfvars`. Here are the key configurations:

### Stack Toggles
*   `enable_dcp` (bool): Set to `true` to deploy the new Data Commons Platform stack (Cloud Run + Spanner).
*   `enable_cdc` (bool): Set to `true` to deploy the legacy Custom Data Commons stack (Cloud Run + MySQL + Redis).

### Data Ingestion Config
*   `dcp_deploy_data_ingestion_workflow` (bool): Set to `true` to deploy the Cloud Workflows orchestrator and ingestion runner service account.
*   `create_ingestion_bucket` (bool): Controls whether Terraform automatically provisions a dedicated staging GCS bucket for uploading graph dataset (.mcf) files. Defaults to `true`.
*   `external_ingestion_bucket_name` (string): If `create_ingestion_bucket` is false, specify an existing external GCS bucket name to attach permissions to.

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

## Running Data Ingestion Workflow

After successful deployment with `dcp_deploy_data_ingestion_workflow = true`, you can run the automated ingestion pipeline.

### Step 1: Upload your Schema file
Upload your custom graph nodes file (`.mcf`) to the provisioned ingestion bucket. By default, the bucket name format is: `<namespace>-ingestion-bucket-<project_id>`.

```bash
gcloud storage cp path/to/your/sample.mcf gs://<namespace>-ingestion-bucket-<project_id>/imports/sample.mcf
```

### Step 2: Trigger the Workflow Orchestrator
Trigger the Cloud Workflow to start the Dataflow job that will read the file and insert it into Spanner.

```bash
gcloud workflows run <namespace>-ingestion-orchestrator \
  --project=<project_id> \
  --location=<region> \
  --data='{
    "templateLocation": "gs://datcom-templates/templates/flex/ingestion.json",
    "region": "<region>",
    "spannerInstanceId": "<spanner-instance-id>",
    "spannerDatabaseId": "<spanner-database-id>",
    "importList": "[{\"importName\": \"SampleTestCase\", \"graphPath\": \"gs://<namespace>-ingestion-bucket-<project_id>/imports/sample.mcf\"}]",
    "tempLocation": "gs://<namespace>-ingestion-bucket-<project_id>/temp"
  }'
```

**Key Data Parameters:**
*   `spannerInstanceId`: The ID of your Spanner instance.
*   `spannerDatabaseId`: The ID of your Spanner database.
*   `importList`: A JSON string mapping the import logical name to the GCS path of the MCF file.

**Tip:** You can use the special flag `"initializeDatabaseOnly": true` in the `--data` JSON payload to just initialize database schemas and skip data parsing.

## Architecture & Troubleshooting

Refer to the original sections in the repository for details on the **Orchestrator Pattern** and resolving common issues like deletion protection errors.
