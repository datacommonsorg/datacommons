#!/usr/bin/env bash
# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ==============================================================================
# Data Commons Platform (DCP) Integration Prober Deployer
# ==============================================================================
# 1. Builds prober container image via Cloud Build.
# 2. Deploys Prober infrastructure (Service Account, Secret Manager, Cloud Run Job,
#    Cloud Scheduler trigger) via Terraform.
# ==============================================================================

set -eo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROBER_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PROBER_DIR}/../../.." && pwd)"

# Auto-detect active gcloud project as default
DETECTED_PROJECT=$(gcloud config get-value project 2>/dev/null || true)
if [[ -z "$DETECTED_PROJECT" || "$DETECTED_PROJECT" == "(unset)" ]]; then
  DETECTED_PROJECT="datcom-dcp"
fi

PROJECT="${DETECTED_PROJECT}"
PROBER_NAME="dcp-prober"
TEST_CONFIG="foobar_wages"
SCHEDULE="0 */3 * * *"
LOCATION="us-central1"
ALERT_EMAIL=""
DC_API_KEY="${DC_API_KEY:-}"
IMAGE_TAG="$(git rev-parse --short HEAD 2>/dev/null || echo "latest")"
NON_INTERACTIVE=false

SKIP_BUILD=false

print_usage() {
  cat <<HELP
DCP Integration Prober Terraform Deployer

Usage:
  $0 [options]

Options:
  --project <id>        GCP Project ID (default: active gcloud project '${PROJECT}')
  --prober-name <name>  Resource name prefix (default: ${PROBER_NAME})
  --test-config <name>  Test manifest name (default: ${TEST_CONFIG})
  --schedule <cron>     Cron schedule for prober (default: "${SCHEDULE}")
  --alert-email <email> Optional email address for failure alerts
  --dc-api-key <key>    Optional Data Commons API Key
  --location <region>   GCP Region (default: ${LOCATION})
  --image-tag <tag>     Custom image tag for registry (default: ${IMAGE_TAG})
  --skip-build          Skip container image build step (reuses existing image)
  --non-interactive     Skip interactive prompts and use defaults/flags
  --help                Show this help message
HELP
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT="$2"
      NON_INTERACTIVE=true
      shift 2
      ;;
    --prober-name)
      PROBER_NAME="$2"
      NON_INTERACTIVE=true
      shift 2
      ;;
    --test-config)
      TEST_CONFIG="$2"
      NON_INTERACTIVE=true
      shift 2
      ;;
    --schedule)
      SCHEDULE="$2"
      NON_INTERACTIVE=true
      shift 2
      ;;
    --alert-email)
      ALERT_EMAIL="$2"
      NON_INTERACTIVE=true
      shift 2
      ;;
    --dc-api-key)
      DC_API_KEY="$2"
      NON_INTERACTIVE=true
      shift 2
      ;;
    --location)
      LOCATION="$2"
      NON_INTERACTIVE=true
      shift 2
      ;;
    --image-tag)
      IMAGE_TAG="$2"
      NON_INTERACTIVE=true
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=true
      shift 1
      ;;
    --non-interactive)
      NON_INTERACTIVE=true
      shift 1
      ;;
    --help|-h)
      print_usage
      exit 0
      ;;
    *)
      echo "Error: Unknown argument: $1"
      print_usage
      exit 1
      ;;
  esac
done

# Interactive Prompting if running in TTY and no flags were passed
if [[ -t 0 && "$NON_INTERACTIVE" == "false" ]]; then
  echo "================================================================================"
  echo "DCP INTEGRATION PROBER INTERACTIVE SETUP"
  echo "================================================================================"
  
  read -p "Enter GCP Project ID [${PROJECT}]: " INPUT_PROJECT
  PROJECT="${INPUT_PROJECT:-$PROJECT}"

  read -p "Enter Prober Resource Name [${PROBER_NAME}]: " INPUT_NAME
  PROBER_NAME="${INPUT_NAME:-$PROBER_NAME}"

  REUSE_SETTINGS=false
  # Check if existing tfvars secret exists
  if gcloud secrets describe "${PROBER_NAME}-tfvars" --project="${PROJECT}" &>/dev/null; then
    ACTIVE_TFVARS=$(gcloud secrets versions access latest --secret="${PROBER_NAME}-tfvars" --project="${PROJECT}" 2>/dev/null || true)
    if [[ -n "$ACTIVE_TFVARS" ]]; then
      SAVED_SCHEDULE=$(echo "$ACTIVE_TFVARS" | grep '^schedule' | head -n 1 | cut -d'"' -f2 || true)
      SAVED_CONFIG=$(echo "$ACTIVE_TFVARS" | grep '^test_config' | head -n 1 | cut -d'"' -f2 || true)
      SAVED_EMAIL=$(echo "$ACTIVE_TFVARS" | grep '^alert_email' | head -n 1 | cut -d'"' -f2 || true)
      SAVED_REGION=$(echo "$ACTIVE_TFVARS" | grep '^region' | head -n 1 | cut -d'"' -f2 || true)

      echo ""
      echo "ℹ️  Found existing deployment settings in Secret Manager (${PROBER_NAME}-tfvars):"
      echo "   • Schedule:    ${SAVED_SCHEDULE:-$SCHEDULE}"
      echo "   • Test Config: ${SAVED_CONFIG:-$TEST_CONFIG}"
      echo "   • Alert Email: ${SAVED_EMAIL:-none}"
      echo "   • Region:      ${SAVED_REGION:-$LOCATION}"
      echo "   • API Key:     [Preserved in Secret Manager]"
      echo ""

      read -p "Do you want to reuse these existing settings? [Y/n]: " REUSE_CHOICE
      REUSE_CHOICE="${REUSE_CHOICE:-Y}"
      if [[ "$REUSE_CHOICE" == "Y" || "$REUSE_CHOICE" == "y" ]]; then
        REUSE_SETTINGS=true
        SCHEDULE="${SAVED_SCHEDULE:-$SCHEDULE}"
        TEST_CONFIG="${SAVED_CONFIG:-$TEST_CONFIG}"
        ALERT_EMAIL="${SAVED_EMAIL:-$ALERT_EMAIL}"
        LOCATION="${SAVED_REGION:-$LOCATION}"
      fi
    fi
  fi

  if [[ "$REUSE_SETTINGS" == "false" ]]; then
    read -p "Enter Cron Schedule [${SCHEDULE}]: " INPUT_SCHEDULE
    SCHEDULE="${INPUT_SCHEDULE:-$SCHEDULE}"

    read -p "Enter Test Config [${TEST_CONFIG}]: " INPUT_CONFIG
    TEST_CONFIG="${INPUT_CONFIG:-$TEST_CONFIG}"

    read -p "Enter GCP Region [${LOCATION}]: " INPUT_LOCATION
    LOCATION="${INPUT_LOCATION:-$LOCATION}"

    read -p "Enter Alert Notification Email (optional) [${ALERT_EMAIL:-none}]: " INPUT_ALERT_EMAIL
    ALERT_EMAIL="${INPUT_ALERT_EMAIL:-$ALERT_EMAIL}"

    read -p "Enter Data Commons API Key (optional) [keep active]: " INPUT_DC_API_KEY
    DC_API_KEY="${INPUT_DC_API_KEY:-$DC_API_KEY}"
  fi
  echo ""
fi

# Strictly scope environment to target project to prevent local active configuration leakage
export GOOGLE_CLOUD_PROJECT="${PROJECT}"
export CLOUDSDK_CORE_PROJECT="${PROJECT}"
export CLOUDSDK_BILLING_QUOTA_PROJECT="${PROJECT}"
export TF_VAR_project_id="${PROJECT}"
export TF_VAR_region="${LOCATION}"
export TF_VAR_prober_name="${PROBER_NAME}"
export TF_VAR_schedule="${SCHEDULE}"
export TF_VAR_test_config="${TEST_CONFIG}"
export TF_VAR_alert_email="${ALERT_EMAIL:-}"
export TF_VAR_dc_api_key="${DC_API_KEY:-}"

REGISTRY_PROJECT="datcom-ci"
REGISTRY_LOCATION="us"
REGISTRY_REPO="datcom-tools"
REGISTRY_BASE="${REGISTRY_LOCATION}-docker.pkg.dev/${REGISTRY_PROJECT}/${REGISTRY_REPO}"
IMAGE_NAME="datacommons-platform-prober"

IMAGE_URI="${REGISTRY_BASE}/${IMAGE_NAME}:${IMAGE_TAG}"
LATEST_IMAGE_URI="${REGISTRY_BASE}/${IMAGE_NAME}:latest"
STATE_BUCKET="tf-state-${PROBER_NAME}-${PROJECT}"
export TF_VAR_container_image="${IMAGE_URI}"

# Check for existing Remote Terraform State
STATE_STATUS="NEW (creating fresh state bucket)"
if gcloud storage buckets describe "gs://${STATE_BUCKET}" --project="${PROJECT}" &>/dev/null; then
  if gcloud storage ls "gs://${STATE_BUCKET}/**" &>/dev/null; then
    STATE_STATUS="EXISTING (will reconnect & update active Prober resources)"
  else
    STATE_STATUS="EXISTING BUCKET (bucket exists, state will be initialized)"
  fi
fi

echo "================================================================================"
echo "DEPLOYING DCP INTEGRATION PROBER VIA TERRAFORM"
echo "  Target GCP Project: ${PROJECT}"
echo "  Registry Project:   ${REGISTRY_PROJECT}"
echo "  Prober Name:        ${PROBER_NAME}"
echo "  Test Config:        ${TEST_CONFIG}"
echo "  Cron Schedule:      ${SCHEDULE}"
echo "  GCP Region:         ${LOCATION}"
echo "  Container Image:    ${IMAGE_URI}"
echo "  Latest Image Tag:   ${LATEST_IMAGE_URI}"
echo "  State Bucket:       gs://${STATE_BUCKET}"
echo "  State Status:       ${STATE_STATUS}"
echo "================================================================================"

# Confirm before proceeding if running interactively
if [[ -t 0 && "$NON_INTERACTIVE" == "false" ]]; then
  echo ""
  read -p "Do you want to proceed with this deployment? [Y/n]: " CONFIRM_DEPLOY
  CONFIRM_DEPLOY="${CONFIRM_DEPLOY:-Y}"
  if [[ "$CONFIRM_DEPLOY" != "Y" && "$CONFIRM_DEPLOY" != "y" ]]; then
    echo "Deployment cancelled by user."
    exit 0
  fi
fi

PROBER_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

# 1. Build and push container image using Cloud Build to datcom-ci (unless skipped)
echo ""
if [[ "$SKIP_BUILD" == "false" ]]; then
  echo "==> Step 1: Building container image via Cloud Build in '${REGISTRY_PROJECT}'..."
  echo "    Prober Commit SHA: ${PROBER_COMMIT:0:8}"
  gcloud builds submit \
    --config="${DEPLOY_DIR}/cloudbuild.yaml" \
    --substitutions="_REGISTRY_BASE=${REGISTRY_BASE},_IMAGE_NAME=${IMAGE_NAME},_PROJECT_ID=${PROJECT},_PROBER_NAME=${PROBER_NAME},_REGION=${LOCATION},_COMMIT_SHA=${PROBER_COMMIT},_TAG=${IMAGE_TAG},_UPDATE_JOB=false" \
    --project="${REGISTRY_PROJECT}" \
    "${REPO_ROOT}"
else
  echo "==> Step 1: Skipping container image build (--skip-build specified). Reusing existing '${IMAGE_URI}'."
fi

# Ensure target project's Cloud Run Service Agent has permission to pull cross-project image from datcom-ci Artifact Registry
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT}" --format="value(projectNumber)" 2>/dev/null || true)
if [[ -n "$PROJECT_NUMBER" ]]; then
  CLOUD_RUN_ROBOT="service-${PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com"
  if ! gcloud artifacts repositories add-iam-policy-binding "${REGISTRY_REPO}" \
    --location="${REGISTRY_LOCATION}" \
    --project="${REGISTRY_PROJECT}" \
    --member="serviceAccount:${CLOUD_RUN_ROBOT}" \
    --role="roles/artifactregistry.reader" &>/dev/null; then
      echo "⚠️  Warning: Could not automatically grant Artifact Registry reader permission on '${REGISTRY_PROJECT}'."
      echo "   If the Cloud Run Job fails to pull the image, please ensure an administrator runs:"
      echo "   gcloud artifacts repositories add-iam-policy-binding ${REGISTRY_REPO} --location=${REGISTRY_LOCATION} --project=${REGISTRY_PROJECT} --member=\"serviceAccount:${CLOUD_RUN_ROBOT}\" --role=\"roles/artifactregistry.reader\""
  fi
fi

# 2. Deploy Prober GCP Infrastructure via Terraform
echo ""
echo "==> Step 2: Provisioning Prober GCP infrastructure via Terraform..."

# Ensure GCS remote state bucket exists
if ! gcloud storage buckets describe "gs://${STATE_BUCKET}" --project="${PROJECT}" &>/dev/null; then
  echo "==> Creating GCS remote state bucket gs://${STATE_BUCKET}..."
  gcloud storage buckets create "gs://${STATE_BUCKET}" --project="${PROJECT}" --location="${LOCATION}"
fi

cd "${DEPLOY_DIR}/terraform"

terraform init -backend-config="bucket=${STATE_BUCKET}" -reconfigure
terraform apply -auto-approve

echo ""
echo "================================================================================"
echo " ✔ PROBER TERRAFORM DEPLOYMENT COMPLETE!"
echo "   Terraform state & variables saved to GCP Secret Manager:"
echo "   Secret ID: ${PROBER_NAME}-tfvars"
echo ""
echo "   To fetch terraform.tfvars anytime, run:"
echo "   gcloud secrets versions access latest --secret=${PROBER_NAME}-tfvars --project=${PROJECT} > terraform.tfvars"
echo "================================================================================"
