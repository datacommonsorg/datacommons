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

PROBER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${PROBER_DIR}/../../.." && pwd)"

PROJECT="datcom-dcp"
TEST_CONFIG="foobar_wages"
SCHEDULE="0 */1 * * *"
LOCATION="us-central1"

print_usage() {
  cat <<HELP
DCP Integration Prober Terraform Deployer

Usage:
  $0 [options]

Options:
  --project <id>        GCP Project ID (default: ${PROJECT})
  --test-config <name>  Test manifest name (default: ${TEST_CONFIG})
  --schedule <cron>     Cron schedule for prober (default: "${SCHEDULE}")
  --location <region>   GCP Region (default: ${LOCATION})
  --help                Show this help message
HELP
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT="$2"
      shift 2
      ;;
    --test-config)
      TEST_CONFIG="$2"
      shift 2
      ;;
    --schedule)
      SCHEDULE="$2"
      shift 2
      ;;
    --location)
      LOCATION="$2"
      shift 2
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

IMAGE_URI="gcr.io/${PROJECT}/dcp-integration-prober:latest"

echo "================================================================================"
echo "DEPLOYING DCP INTEGRATION PROBER VIA TERRAFORM"
echo "  Project ID:       ${PROJECT}"
echo "  Test Config:      ${TEST_CONFIG}"
echo "  Cron Schedule:    ${SCHEDULE}"
echo "  Container Image:  ${IMAGE_URI}"
echo "================================================================================"

# 1. Build and push container image using Cloud Build
echo ""
echo "==> Step 1: Building container image via Cloud Build..."
gcloud builds submit \
  --config=/dev/null \
  --tag="${IMAGE_URI}" \
  --project="${PROJECT}" \
  --file=tests/integration/prober/Dockerfile \
  "${REPO_ROOT}"

# 2. Deploy Prober GCP Infrastructure via Terraform
echo ""
echo "==> Step 2: Provisioning Prober GCP infrastructure via Terraform..."
STATE_BUCKET="tf-state-dcp-prober-${PROJECT}"

# Ensure GCS remote state bucket exists
gcloud storage buckets create "gs://${STATE_BUCKET}" --project="${PROJECT}" --location="${LOCATION}" 2>/dev/null || true

cd "${PROBER_DIR}/terraform"

terraform init -backend-config="bucket=${STATE_BUCKET}" -reconfigure
terraform apply -auto-approve \
  -var="project_id=${PROJECT}" \
  -var="region=${LOCATION}" \
  -var="container_image=${IMAGE_URI}" \
  -var="schedule=${SCHEDULE}" \
  -var="test_config=${TEST_CONFIG}"

echo ""
echo "================================================================================"
echo " ✔ PROBER TERRAFORM DEPLOYMENT COMPLETE!"
echo "   Terraform state & variables saved to GCP Secret Manager:"
echo "   Secret ID: dcp-prober-tfvars"
echo ""
echo "   To fetch terraform.tfvars anytime, run:"
echo "   gcloud secrets versions access latest --secret=dcp-prober-tfvars --project=${PROJECT} > terraform.tfvars"
echo "================================================================================"
