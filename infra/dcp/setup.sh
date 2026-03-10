#!/bin/bash
# setup.sh
# Configures the Terraform GCS Backend for state storage.

set -e

echo "Welcome to the Data Commons Infrastructure Setup!"
echo "This script will configure your Terraform state to be stored in a Google Cloud Storage bucket."
echo ""

# Check for terraform.tfvars file
if [ ! -f terraform.tfvars ]; then
    echo "⚠️  Warning: No terraform.tfvars file found. You might want to copy terraform.tfvars.example to terraform.tfvars first."
fi

# Prompt for bucket name
read -p "Enter the name of your GCS Terraform State Bucket: " BUCKET_NAME

if [ -z "$BUCKET_NAME" ]; then
    echo "Error: Bucket name cannot be empty."
    exit 1
fi

# Prioritize project_id from terraform.tfvars if it exists
if [ -f terraform.tfvars ]; then
    PROJECT_ID=$(grep "^project_id" terraform.tfvars | awk -F'=' '{print $2}' | tr -d ' "')
fi

# Fallback to .env (for backward compatibility during transition)
if [ -z "$PROJECT_ID" ] && [ -f .env ]; then
    PROJECT_ID=$(grep "^TF_VAR_project_id" .env | awk -F'=' '{print $2}' | tr -d ' "')
fi

# Fallback to GOOGLE_CLOUD_PROJECT
if [ -z "$PROJECT_ID" ] && [ -n "$GOOGLE_CLOUD_PROJECT" ]; then
    PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
fi

# Final prompting if still missing
if [ -z "$PROJECT_ID" ]; then
    read -p "Enter your Google Cloud Project ID: " PROJECT_ID
fi

# Create the bucket if it doesn't exist
echo "Checking bucket gs://${BUCKET_NAME}..."
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "Creating bucket gs://${BUCKET_NAME} in ${PROJECT_ID}..."
    gcloud storage buckets create "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" --location=us --uniform-bucket-level-access
    
    echo "Enabling versioning on gs://${BUCKET_NAME}..."
    gcloud storage buckets update "gs://${BUCKET_NAME}" --versioning
else
    echo "Bucket gs://${BUCKET_NAME} already exists."
fi

# Generate the backend.tf file dynamically
echo "Generating backend.tf..."
cat <<EOF > backend.tf
terraform {
  backend "gcs" {
    bucket = "${BUCKET_NAME}"
    prefix = "terraform/state"
  }
}
EOF

echo "✅ backend.tf created successfully!"
echo "Now running terraform init..."
terraform init

echo ""
echo "Setup complete! You can now run 'terraform apply' to deploy your infrastructure."
