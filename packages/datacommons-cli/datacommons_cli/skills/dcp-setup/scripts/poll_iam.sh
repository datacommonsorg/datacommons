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

# Main orchestrator (Table of Contents)
main() {
    validate_args "$@"
    
    local project_id="$1"
    local sa_email="$2"
    local user_email="$3"
    
    apply_policy_binding "${project_id}" "${sa_email}" "${user_email}"
    poll_token_propagation "${sa_email}"
}

# Validate CLI Arguments
validate_args() {
    if [[ $# -lt 3 ]]; then
        log_error "Usage: $0 <PROJECT_ID> <ORCHESTRATOR_SA_EMAIL> <ACTIVE_USER_EMAIL>"
        exit 1
    fi
}

# Apply IAM Impersonation Policy Binding
apply_policy_binding() {
    local project_id="$1"
    local sa_email="$2"
    local user_email="$3"
    
    log_info "Configuring IAM Service Account Impersonation bindings..."
    log_info "Project: ${project_id}"
    log_info "Service Account: ${sa_email}"
    log_info "User: ${user_email}"
    
    if gcloud iam service-accounts add-iam-policy-binding "${sa_email}" \
        --member="user:${user_email}" \
        --role="roles/iam.serviceAccountTokenCreator" \
        --project="${project_id}" &>/dev/null; then
        log_success "Successfully applied Token Creator binding to service account!"
    else
        log_error "Failed to bind roles/iam.serviceAccountTokenCreator on service account."
        exit 1
    fi
    
    log_info "IAM permission changes submitted to GCP."
}

# Poll for IAM propagation until success
poll_token_propagation() {
    local sa_email="$1"
    
    log_info "Starting active verification loop (impersonation token polling)..."
    
    local max_attempts=16
    local wait_interval=15
    local success=false
    
    # Create a single temporary file outside the loop and ensure cleanup on exit
    local err_out
    err_out="$(mktemp)"
    trap 'rm -f "${err_out}"' EXIT
    
    for ((attempt=1; attempt<=max_attempts; attempt++)); do
        log_info "Attempt $attempt of $max_attempts: Requesting access token via impersonation..."
        
        if gcloud auth print-access-token --impersonate-service-account="${sa_email}" &>/dev/null 2>"${err_out}"; then
            log_success "GCP impersonation propagated successfully! Access token generated."
            success=true
            break
        else
            local err_msg
            err_msg="$(cat "${err_out}" | tr -d '\n')"
            log_warning "Propagation pending (Details: ${err_msg}). Waiting ${wait_interval}s before retry..."
            sleep ${wait_interval}
        fi
    done
    
    if [ "${success}" = true ]; then
        log_success "IAM bindings are completely propagated and active!"
        exit 0
    else
        log_error "IAM permissions failed to propagate within $((max_attempts * wait_interval)) seconds."
        log_error "Please manually verify that user has impersonation privileges on ${sa_email}."
        exit 1
    fi
}

# Execution Trigger (Must remain at the bottom of the script)
main "$@"
