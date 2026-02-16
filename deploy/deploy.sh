#!/bin/bash
set -e

# Ensure we are in the script's directory (resilient execution)
cd "$(dirname "$0")"

# =============================================================================
# 1. SETUP & CONFIGURATION
# =============================================================================
ENV_NAME=${1:-dev}
ENV_FILE="env.${ENV_NAME}"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: Configuration file '$ENV_FILE' not found!"
    exit 1
fi

# Load variables
set -a
source "$ENV_FILE"
set +a

# Define file names
# Define file names
TEMPLATE_FILE="service.yaml.template"
GENERATED_FILE="service.generated.yaml"

# =============================================================================
# 2. PREPARE NGINX CONFIG (The Injection Step)
# =============================================================================
echo "📄 Encoding nginx.conf..."
if [ ! -f "nginx.conf" ]; then
    echo "❌ Error: nginx.conf not found!"
    exit 1
fi

# Detect OS for correct Base64 flags (Mac vs Linux)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    export NGINX_CONFIG_B64=$(base64 -i nginx.conf)
else
    # Linux (Cloud Build / CI / Ubuntu)
    export NGINX_CONFIG_B64=$(base64 -w 0 nginx.conf)
fi

# =============================================================================
# 3. GENERATE YAML
# =============================================================================
echo "🛠️  Generating configuration..."
# envsubst replaces ${NGINX_CONFIG_B64} with the massive string
envsubst < "$TEMPLATE_FILE" > "$GENERATED_FILE"

# =============================================================================
# 4. MANUAL REVIEW
# =============================================================================
echo "--------------------------------------------------------"
echo "📄 REVIEW GENERATED CONFIGURATION"
echo "--------------------------------------------------------"
# Print summary (Printing the whole file might be messy with the huge b64 string)
echo "   Service:     $SERVICE_NAME"
echo "   Project:     $GCP_PROJECT_ID"
echo "   Config File: $GENERATED_FILE"
echo "   Env File:    $ENV_FILE"
echo ""
echo "👉 You can inspect '$GENERATED_FILE' in another terminal or editor before confirming."

read -p "❓ Do you want to deploy this configuration? (y/N): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "❌ Deployment ABORTED."
    rm "$GENERATED_FILE"
    exit 1
fi

# =============================================================================
# 5. EXECUTE DEPLOYMENT
# =============================================================================
echo "🚀 Deploying to Cloud Run..."
gcloud run services replace "$GENERATED_FILE" \
    --region="$GCP_REGION" \
    --project="$GCP_PROJECT_ID"

rm "$GENERATED_FILE"
echo "✅ SUCCESS!"