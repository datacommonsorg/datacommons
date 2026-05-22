#!/usr/bin/env bash
#
# Data Commons Platform (DCP) - IAM Token Impersonation Poller
# Binds serviceAccountTokenCreator privileges and polls until propagation succeeds.
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0;0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

if [[ $# -lt 3 ]]; then
    log_error "Usage: $0 <PROJECT_ID> <ORCHESTRATOR_SA_EMAIL> <ACTIVE_USER_EMAIL>"
    exit 1
fi

PROJECT_ID="$1"
SA_EMAIL="$2"
USER_EMAIL="$3"

log_info "Configuring IAM Service Account Impersonation bindings..."
log_info "Project: ${PROJECT_ID}"
log_info "Service Account: ${SA_EMAIL}"
log_info "User: ${USER_EMAIL}"

# Apply the binding
if gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
    --member="user:${USER_EMAIL}" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --project="${PROJECT_ID}" &>/dev/null; then
    log_success "Successfully applied Token Creator binding to service account!"
else
    log_error "Failed to bind roles/iam.serviceAccountTokenCreator on service account."
    exit 1
fi

log_info "IAM permission changes submitted to GCP."
log_info "Starting active verification loop (impersonation token polling)..."

MAX_ATTEMPTS=16
WAIT_INTERVAL=15
SUCCESS=false

for ((attempt=1; attempt<=MAX_ATTEMPTS; attempt++)); do
    log_info "Attempt $attempt of $MAX_ATTEMPTS: Requesting access token via impersonation..."
    
    # Redirect stderr to a temporary file to check for permission errors
    ERR_OUT=$(mktemp)
    
    if gcloud auth print-access-token --impersonate-service-account="${SA_EMAIL}" &>/dev/null 2>"${ERR_OUT}"; then
        log_success "GCP impersonation propagated successfully! Access token generated."
        SUCCESS=true
        rm -f "${ERR_OUT}"
        break
    else
        ERR_MSG=$(cat "${ERR_OUT}")
        rm -f "${ERR_OUT}"
        
        log_warning "Permission propagation pending. Waiting ${WAIT_INTERVAL}s before retry..."
        sleep ${WAIT_INTERVAL}
    fi
done

if [ "$SUCCESS" = true ]; then
    log_success "IAM bindings are completely propagated and active!"
    exit 0
else
    log_error "IAM permissions failed to propagate within $((MAX_ATTEMPTS * WAIT_INTERVAL)) seconds."
    log_error "Please manually verify that user has impersonation privileges on ${SA_EMAIL}."
    exit 1
fi
