#!/bin/bash
set -e

# Ensure we are in the deploy root (parent of scripts/)
cd "$(dirname "$0")/.."

# =============================================================================
# 1. SETUP & CONFIGURATION
# =============================================================================
ENV_NAME=${1:-dev}
ENV_FILE="envs/${ENV_NAME}/env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: Configuration file '$ENV_FILE' not found!"
    exit 1
fi

echo "📂 Loading configuration for: $ENV_NAME"
# Load environment variables
set -a
source "$ENV_DIR/env"
set +a

# Define Template Paths
TEMPLATE_FILE="templates/services.yaml.template"
NGINX_FILE="templates/nginx.conf"
MIXER_FLAGS_FILE="$ENV_DIR/mixer_flags.yaml"
GENERATED_FILE="services.generated.yaml"
# =============================================================================
# 2. PREPARE INJECTIONS (Base64 Encoding)
# =============================================================================

# A. NGINX CONFIG
echo "📄 Encoding Nginx Config..."
if [ ! -f "$NGINX_FILE" ]; then
    echo "❌ Error: $NGINX_FILE not found!"
    exit 1
fi
if [[ "$OSTYPE" == "darwin"* ]]; then
    export NGINX_CONFIG_B64=$(base64 -i "$NGINX_FILE")
else
    export NGINX_CONFIG_B64=$(base64 -w 0 "$NGINX_FILE")
fi

# B. MIXER FEATURE FLAGS
echo "🚩 Encoding Feature Flags..."
if [ ! -f "$MIXER_FLAGS_FILE" ]; then
    echo "⚠️  Warning: $MIXER_FLAGS_FILE not found. Using empty flags."
    export MIXER_FEATURE_FLAGS_B64=""
else
    if [[ "$OSTYPE" == "darwin"* ]]; then
        export MIXER_FEATURE_FLAGS_B64=$(base64 -i "$MIXER_FLAGS_FILE")
    else
        export MIXER_FEATURE_FLAGS_B64=$(base64 -w 0 "$MIXER_FLAGS_FILE")
    fi
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