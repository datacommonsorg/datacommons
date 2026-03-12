#!/bin/bash
# update_image_tag.sh
# Updates the dcp_image_tag in terraform.tfvars with the latest version from Artifact Registry.

set -e

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
IMAGE_BASE="us-docker.pkg.dev/datcom-ci/gcr.io/datacommons-platform"
TFVARS_FILE="${SCRIPT_DIR}/terraform.tfvars"

echo "🔍 Preparing to update image tag..."

# 1. Extract Details
# Parse Project, Repo, and Package from IMAGE_BASE
# Assumes format: LOCATION-docker.pkg.dev/PROJECT/REPO/PACKAGE
REG_PROJECT=$(echo "$IMAGE_BASE" | cut -d'/' -f2)
REG_REPO=$(echo "$IMAGE_BASE" | cut -d'/' -f3)
REG_PACKAGE=$(echo "$IMAGE_BASE" | cut -d'/' -f4)
REG_LOCATION=$(echo "$IMAGE_BASE" | cut -d'-' -f1)

if [ -z "$REG_PROJECT" ] || [ -z "$REG_REPO" ] || [ -z "$REG_PACKAGE" ]; then
    echo "❌ Error: Could not parse registry details from $IMAGE_BASE"
    exit 1
fi

# 2. Determine the tag
if [ "$1" ]; then
    TAG="$1"
    echo "📍 Using manually specified tag: $TAG"
else
    echo "🌐 Fetching latest tag from Artifact Registry ($REG_PROJECT)..."
    
    # Logic: 
    # 1. Find which image version is currently tagged as 'latest'
    # 2. Find all tags associated with that version (e.g. the commit SHA)
    # 3. Pick the one that ISN'T 'latest'
    
    VERSION_ID=$(gcloud artifacts tags list \
        --project="$REG_PROJECT" \
        --location="$REG_LOCATION" \
        --repository="$REG_REPO" \
        --package="$REG_PACKAGE" \
        --filter="name:latest" \
        --format="value(version)" \
        --limit=1 2>/dev/null || true)

    if [ -z "$VERSION_ID" ]; then
        echo "❌ Error: Could not find version with tag 'latest' in $IMAGE_BASE"
        exit 1
    fi
    
    echo "✅ Newest image version (tagged as 'latest'): $VERSION_ID"

    # Get all tags for this specific version ID
    ALL_TAGS=$(gcloud artifacts tags list \
        --project="$REG_PROJECT" \
        --location="$REG_LOCATION" \
        --repository="$REG_REPO" \
        --package="$REG_PACKAGE" \
        --filter="version:$VERSION_ID" \
        --format="value(TAG)")

    if [ -z "$ALL_TAGS" ]; then
        echo "⚠️  No specific tags found for this version. Falling back to 'latest'."
        TAG="latest"
    else
        # Pick the first tag that is NOT exactly 'latest'
        TAG=$(echo "$ALL_TAGS" | tr ' ' '\n' | grep -v "^latest$" | head -n 1)
        
        # Fallback to latest if no other tag exists
        if [ -z "$TAG" ]; then
            TAG="latest"
        fi
        echo "✅ Detected alternative tag: $TAG"
    fi
fi

# 3. Update terraform.tfvars
echo "📝 Updating $TFVARS_FILE..."

# Check if dcp_image_tag already exists
if grep -q "^dcp_image_tag" "$TFVARS_FILE"; then
    # Use sed to replace the line. (Special syntax for macOS)
    sed -i '' "s/^dcp_image_tag.*/dcp_image_tag = \"$TAG\"/" "$TFVARS_FILE"
else
    # Append to end of file if it doesn't exist
    echo "" >> "$TFVARS_FILE"
    echo "dcp_image_tag = \"$TAG\"" >> "$TFVARS_FILE"
fi

echo "✨ Success! image tag is now set to \"$TAG\" in $TFVARS_FILE."
echo "You can now run 'terraform plan' to see the changes."
