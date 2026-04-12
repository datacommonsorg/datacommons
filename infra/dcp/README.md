# Data Commons Platform (DCP) Infrastructure

This directory contains the Terraform configuration to deploy the Data Commons Platform on Google Cloud Platform (GCP).

## Prerequisites
*   **GCP Project**: A GCP project with billing enabled.
*   **Terraform**: Terraform installed locally (>= 1.0.0).
*   **gcloud CLI**: GCP CLI installed and authenticated.

## Setup

1.  **Configure Local Variables**:
    Copy the example variable file and fill in your project details.
    ```bash
    cp terraform.tfvars.example terraform.tfvars
    ```
    Edit `terraform.tfvars` with your `project_id` and other preferred settings.

2.  **Run Setup Script**:
    The `setup.sh` script creates a GCS bucket for your Terraform state and initializes the backend.
    ```bash
    ./setup.sh
    ```

## Deployment

1.  **Initialize**:
    Initialize Terraform (if not already done by setup.sh).
    ```bash
    terraform init
    ```

2.  **Plan**:
    Review the changes Terraform will make.
    ```bash
    terraform plan
    ```

3.  **Apply**:
    Provision the infrastructure.
    ```bash
    terraform apply
    ```

4.  **Teardown**:
    Destroy all resources.
    ```bash
    terraform destroy
    ```

## Architecture

This setup uses an **Orchestrator Pattern**:
- `infra/dcp/main.tf`: The root entrypoint that calls modules.
- `infra/dcp/modules/dcp/`: The new Data Commons Platform stack (Cloud Run + Spanner).
- `infra/dcp/modules/cdc/`: The legacy Custom Data Commons stack (Cloud Run + MySQL + Redis).

Each module is independent and can be toggled via the root variables in `terraform.tfvars`.

## Troubleshooting
*   **Deletion Errors**: If you get a "cannot destroy... deletion_protection" error, ensure `deletion_protection = false` in your `terraform.tfvars`, run `terraform apply`, and then try `terraform destroy` again. Alternatively, use the helper command:
    ```bash
    make force-destroy
    ```
