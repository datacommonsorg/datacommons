#!/bin/bash
# ==============================================================================
# deploy.sh
#
# Script to configure and deploy the DataCommons Cloud Run service.
#
# Usage:
#   ./deploy/scripts/deploy.sh [ENV_NAME] [--no-dry-run]
#
# Arguments:
#   ENV_NAME        The environment to deploy to (e.g., 'dev', 'prod').
#                   Defaults to 'dev'.
#   --no-dry-run    If specified, applies the deployment to Cloud Run.
#                   By default, it performs a validation-only dry run.
#
# Examples:
#   # Dry run for 'dev' environment (default)
#   ./deploy/scripts/deploy.sh
#
#   # Dry run for 'prod' environment
#   ./deploy/scripts/deploy.sh prod
#
#   # Actual deployment for 'dev' environment
#   ./deploy/scripts/deploy.sh dev --no-dry-run
# ==============================================================================
set -e

# Ensure we are in the deploy root
cd "$(dirname "$0")/.."

# =============================================================================
# 1. SETUP & CONFIGURATION
# =============================================================================

# Default values
ENV_NAME="dev"
DRY_RUN="true"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --no-dry-run)
      DRY_RUN="false"
      shift
      ;;
    *)
      ENV_NAME="$1"
      shift
      ;;
  esac
done

if [[ "$DRY_RUN" == "true" ]]; then
    echo "⚠️  DRY RUN MODE: No changes will be applied to Cloud Run."
    echo "    Use '--no-dry-run' to execute the deployment."
else
    echo "🚨 PRODUCTION MODE: Changes WILL be applied to Cloud Run."
fi

ENV_DIR="envs/${ENV_NAME}"
ENV_FILE="${ENV_DIR}/env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: Configuration file '$ENV_FILE' not found!"
    exit 1
fi

echo "📂 Loading configuration for: $ENV_NAME"
set -a
source "$ENV_DIR/env"
set +a

# Define Template Paths
TEMPLATE_FILE="templates/service.yaml.template"
NGINX_FILE="templates/nginx.conf"
MIXER_FLAGS_FILE="$ENV_DIR/mixer_flags.yaml"
GENERATED_FILE="/tmp/service.generated.yaml"

# =============================================================================
# 2. HELPER FUNCTIONS
# =============================================================================

# Usage: encode_file_to_var "InputFilePath" "OutputVarName"
encode_file_to_var() {
    local file_path="$1"
    local var_name="$2"

    if [ ! -f "$file_path" ]; then
        echo "⚠️  Warning: File '$file_path' not found. Setting $var_name to empty."
        export "$var_name"=""
        return
    fi

    echo "📄 Encoding $file_path -> \$$var_name..."
    
    # Detect OS for correct Base64 flags (Linux uses -w 0, Mac uses -b 0 to disable wrapping)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        encoded=$(base64 -i "$file_path" -b 0)
    else
        # Linux
        encoded=$(base64 -w 0 "$file_path")
    fi

    # Export the variable dynamically
    export "$var_name"="$encoded"
}

# =============================================================================
# 3. PREPARE INJECTIONS
# =============================================================================

# Now the logic is clean and reusable:
encode_file_to_var "$NGINX_FILE" "NGINX_CONFIG_B64"
encode_file_to_var "$MIXER_FLAGS_FILE" "MIXER_FEATURE_FLAGS_B64"


# =============================================================================
# 4. GENERATE YAML
# =============================================================================
echo "🛠️  Generating configuration..."
envsubst < "$TEMPLATE_FILE" > "$GENERATED_FILE"

# =============================================================================
# 5. MANUAL REVIEW
# =============================================================================
echo "--------------------------------------------------------"
echo "📄 REVIEW GENERATED CONFIGURATION"
echo "--------------------------------------------------------"
echo "   Service:     $SERVICE_NAME"
echo "   Cloud Run:   $CLOUD_RUN_SERVICE_NAME"
echo "   Project:     $GCP_PROJECT_ID"
echo "   Config File: $GENERATED_FILE"
echo ""
echo "👉 You can inspect '$GENERATED_FILE' in another terminal or editor before confirming."


if [[ "$DRY_RUN" == "true" ]]; then
    echo ""
    echo "🏃 DRY RUN: validating service configuration with Cloud Run..."
    gcloud run services replace "$GENERATED_FILE" \
        --region="$GCP_REGION" \
        --project="$GCP_PROJECT_ID" \
        --dry-run

    echo "✅ DRY RUN COMPLETE. Configuration appears valid."
    echo "   Use '--no-dry-run' to actually deploy."
    exit 0
fi

read -p "❓ Do you want to deploy this configuration? (y/N): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "❌ Deployment ABORTED."
    exit 1
fi

# =============================================================================
# 6. EXECUTE DEPLOYMENT
# =============================================================================
echo "🚀 Deploying to Cloud Run..."
# Use --quiet to suppress the "Do you want to continue" prompt since we already asked
gcloud run services replace "$GENERATED_FILE" \
    --region="$GCP_REGION" \
    --project="$GCP_PROJECT_ID" \
    --quiet

echo "✅ SUCCESS!"