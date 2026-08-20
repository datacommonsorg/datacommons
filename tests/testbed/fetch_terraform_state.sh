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
# Data Commons Platform (DCP) Developer Testbed CLI
# ==============================================================================
# Enables rapid connection, configuration synchronization, and IAM impersonation
# for shared and developer testbeds in Google Cloud Platform.
# ==============================================================================

set -eo pipefail

# Find repository root and testbed directories
TESTBED_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${TESTBED_DIR}/../.." && pwd)"
WORKSPACES_ROOT="${TESTBED_DIR}/workspaces"
INFRA_DCP_DIR="${REPO_ROOT}/infra/dcp"

# Default project if not specified
DEFAULT_PROJECT="datcom-dcp"

print_usage() {
  cat <<HELP
Data Commons Platform - Developer Testbed CLI

Usage:
  $0 <command> [options]

Commands:
  connect       Connect to a testbed (pulls config, inits Terraform, checks IAM impersonation)
  push-config   Save and push local terraform.tfvars back to GCP Secret Manager
  list          List available testbeds in the project

Options:
  --instance <name>   Instance name (e.g. testbed-1, testbed-alpha, alice)
  --project <id>      GCP Project ID (default: ${DEFAULT_PROJECT})

Developer Workflow:
  1. Connect to an instance (interactive or via flag):
     $0 connect --instance testbed-1

  2. Navigate to your workspace, edit terraform.tfvars, and apply:
     cd tests/testbed/workspaces/testbed-1
     terraform apply

  3. Push your updated configuration back to the team secret:
     $0 push-config --instance testbed-1

  4. List all active testbeds:
     $0 list
HELP
}

# Ensure dependencies exist
check_dependencies() {
  local missing=0

  if ! command -v gcloud &>/dev/null; then
    echo "Error: 'gcloud' CLI is not installed or not in PATH."
    echo "  Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
    missing=1
  fi

  if ! command -v terraform &>/dev/null; then
    echo "Error: 'terraform' CLI is not installed or not in PATH."
    echo "  Install Terraform: https://developer.hashicorp.com/terraform/install"
    missing=1
  fi

  if [[ $missing -eq 1 ]]; then
    return 1
  fi

  # Check for datacommons CLI (warning if not in PATH or uv)
  if ! command -v datacommons &>/dev/null && ! uv run datacommons --help &>/dev/null 2>&1; then
    echo "Notice: 'datacommons' CLI is not installed in PATH."
    echo "  To run ingestion/workflow CLI commands, install it via: pip install -e packages/datacommons-cli"
    echo "  (or execute via: uv run datacommons <command>)"
    echo ""
  fi
  return 0
}

# Interactive prompt to select or enter an instance if --instance was omitted
prompt_instance_if_missing() {
  if [[ -n "$INSTANCE" ]]; then
    return 0
  fi

  # If not running interactively (e.g. CI/CD), error out
  if [[ ! -t 0 ]]; then
    echo "Error: --instance <name> is required in non-interactive mode."
    return 1
  fi

  echo "==> No --instance provided. Querying available testbeds in '${PROJECT}'..."
  local secrets
  secrets=$(gcloud secrets list --project="${PROJECT}" --format="value(name)" 2>/dev/null || true)

  local options=()
  for s in $secrets; do
    local secret_id
    secret_id=$(basename "$s")
    if [[ "$secret_id" =~ ^dcp-(.+)-tfvars$ ]]; then
      options+=("${BASH_REMATCH[1]}")
    fi
  done

  echo ""
  if [[ ${#options[@]} -gt 0 ]]; then
    echo "Available testbeds:"
    local i=1
    for opt in "${options[@]}"; do
      echo "  $i) $opt"
      ((i++))
    done
    echo "  $i) [Enter a custom instance name]"
    echo ""
    read -p "Select a testbed (1-$i): " choice

    if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice < i )); then
      INSTANCE="${options[$((choice - 1))]}"
    elif [[ "$choice" =~ ^[0-9]+$ ]] && (( choice == i )); then
      read -p "Enter instance name: " custom_name
      INSTANCE="$custom_name"
    else
      # If user typed the name directly
      INSTANCE="$choice"
    fi
  else
    read -p "No existing testbeds found. Enter instance name to create/connect: " INSTANCE
  fi

  if [[ -z "$INSTANCE" ]]; then
    echo "Error: Instance name cannot be empty."
    return 1
  fi

  echo "==> Selected instance: '$INSTANCE'"
  echo ""
  return 0
}

main() {
  local ACTION="$1"
  if [[ "$ACTION" == "--help" || "$ACTION" == "-h" ]]; then
    print_usage
    return 0
  elif [[ "$ACTION" == "connect" || "$ACTION" == "push-config" || "$ACTION" == "list" ]]; then
    shift
  elif [[ "$ACTION" == --* || -z "$ACTION" ]]; then
    ACTION="connect"
  else
    echo "Error: Unknown command '$ACTION'"
    print_usage
    return 1
  fi

  INSTANCE=""
  PROJECT="$DEFAULT_PROJECT"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --instance)
        INSTANCE="$2"
        shift 2
        ;;
      --project)
        PROJECT="$2"
        shift 2
        ;;
      --help|-h)
        print_usage
        return 0
        ;;
      *)
        echo "Error: Unknown option: $1"
        print_usage
        return 1
        ;;
    esac
  done

  # Auto-infer instance name if running inside a workspace folder (e.g. tests/testbed/workspaces/testbed-1)
  if [[ -z "$INSTANCE" ]]; then
    local CURRENT_DIR
    CURRENT_DIR="$(pwd)"
    if [[ "$CURRENT_DIR" == *"/workspaces/"* ]]; then
      INSTANCE="$(basename "$CURRENT_DIR")"
      echo "==> Auto-detected instance '$INSTANCE' from current directory."
    fi
  fi

  if ! check_dependencies; then
    return 1
  fi

  # ==============================================================================
  # ACTION: LIST
  # ==============================================================================
  if [[ "$ACTION" == "list" ]]; then
    echo "================================================================================"
    echo "DCP TESTBEDS in project: ${PROJECT}"
    echo "================================================================================"
    
    echo "Fetching registered testbed secrets from Secret Manager..."
    local SECRETS
    SECRETS=$(gcloud secrets list --project="${PROJECT}" --format="value(name)" 2>/dev/null || true)

    local found=0
    local options=()
    for s in $SECRETS; do
      local secret_id
      secret_id=$(basename "$s")
      if [[ "$secret_id" =~ ^dcp-(.+)-tfvars$ ]]; then
        if [[ $found -eq 0 ]]; then
          printf "%-5s %-25s %-35s\n" "#" "INSTANCE NAME" "SECRET NAME"
          printf "%-5s %-25s %-35s\n" "--" "-------------" "-----------"
        fi
        local inst_name="${BASH_REMATCH[1]}"
        options+=("$inst_name")
        found=$((found + 1))
        printf "%-5s %-25s %-35s\n" "$found" "$inst_name" "$secret_id"
      fi
    done

    if [[ $found -eq 0 ]]; then
      echo "No 'dcp-*-tfvars' secrets found in project '${PROJECT}'."
      return 0
    fi

    # If running interactively, prompt to connect directly
    if [[ -t 0 ]]; then
      echo ""
      read -p "Select a testbed to connect to [1-$found, or press Enter to exit]: " choice
      if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= found )); then
        INSTANCE="${options[$((choice - 1))]}"
        ACTION="connect"
        echo ""
      else
        return 0
      fi
    else
      return 0
    fi
  fi

  if ! prompt_instance_if_missing; then
    return 1
  fi

  local SECRET_NAME="dcp-${INSTANCE}-tfvars"
  local WORKSPACE_DIR="${WORKSPACES_ROOT}/${INSTANCE}"
  local STATE_BUCKET="tf-state-${INSTANCE}-${PROJECT}"

  # ==============================================================================
  # ACTION: CONNECT
  # ==============================================================================
  if [[ "$ACTION" == "connect" ]]; then
    echo "==> [1/5] Connecting to testbed '${INSTANCE}' in project '${PROJECT}'..."
    mkdir -p "$WORKSPACE_DIR"

    echo "==> [2/5] Pulling configuration from Secret Manager ($SECRET_NAME)..."
    if [[ -f "$WORKSPACE_DIR/terraform.tfvars" ]]; then
      cp "$WORKSPACE_DIR/terraform.tfvars" "$WORKSPACE_DIR/terraform.tfvars.bak"
    fi

    if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" &>/dev/null; then
      gcloud secrets versions access latest \
        --secret="$SECRET_NAME" \
        --project="$PROJECT" > "$WORKSPACE_DIR/terraform.tfvars"
      echo "    Successfully fetched terraform.tfvars from Secret Manager."
    else
      echo "    Warning: Secret '$SECRET_NAME' does not exist in Secret Manager."
      if [[ ! -f "$WORKSPACE_DIR/terraform.tfvars" ]]; then
        echo "    Creating new boilerplate terraform.tfvars for '${INSTANCE}'..."
        cat <<TFVARS > "$WORKSPACE_DIR/terraform.tfvars"
project_id    = "${PROJECT}"
instance_name = "${INSTANCE}"
region        = "us-central1"
TFVARS
      fi
    fi

    # Copy root terraform definition files into workspace and symlink modules
    echo "==> [3/5] Syncing Terraform scaffolding..."
    cp "${INFRA_DCP_DIR}"/*.tf "$WORKSPACE_DIR/"
    ln -sfn "${INFRA_DCP_DIR}/modules" "$WORKSPACE_DIR/modules"

    echo "==> [4/5] Setting up remote GCS backend state..."
    cat <<BACKEND > "$WORKSPACE_DIR/backend.tf"
terraform {
  backend "gcs" {
    bucket = "${STATE_BUCKET}"
    prefix = "terraform/state/${INSTANCE}"
  }
}
BACKEND

    (
      cd "$WORKSPACE_DIR"
      echo "    Running terraform init..."
      terraform init
    )

    # Check & configure service account impersonation for CLI commands
    echo "==> [5/5] Checking Service Account impersonation permissions..."
    local CURRENT_USER
    CURRENT_USER=$(gcloud config get-value account 2>/dev/null || true)
    local WORKFLOW_SA
    WORKFLOW_SA=$(cd "$WORKSPACE_DIR" && terraform output -raw ingestion_workflow_service_account_email 2>/dev/null || true)

    if [[ -n "$CURRENT_USER" && -n "$WORKFLOW_SA" ]]; then
      echo "    Authenticated user: ${CURRENT_USER}"
      echo "    Workflow Service Account: ${WORKFLOW_SA}"
      
      # Check if user already has TokenCreator role using precise gcloud filter
      local HAS_ROLE
      HAS_ROLE=$(gcloud iam service-accounts get-iam-policy "$WORKFLOW_SA" \
        --project="$PROJECT" \
        --filter="bindings.role=roles/iam.serviceAccountTokenCreator AND bindings.members=user:${CURRENT_USER}" \
        --format="value(bindings.role)" 2>/dev/null || true)

      if [[ -z "$HAS_ROLE" ]]; then
        echo "    Granting 'roles/iam.serviceAccountTokenCreator' to user:${CURRENT_USER} on ${WORKFLOW_SA}..."
        if gcloud iam service-accounts add-iam-policy-binding "$WORKFLOW_SA" \
             --member="user:${CURRENT_USER}" \
             --role="roles/iam.serviceAccountTokenCreator" \
             --project="$PROJECT" --quiet &>/dev/null; then
          echo "    ✔ Successfully configured Service Account impersonation."
        else
          echo "    Notice: Could not automatically grant TokenCreator permission (insufficient IAM admin rights)."
          echo "    If you plan to run ingestion CLI commands, ask a project admin to run:"
          echo "      gcloud iam service-accounts add-iam-policy-binding \"${WORKFLOW_SA}\" --member=\"user:${CURRENT_USER}\" --role=\"roles/iam.serviceAccountTokenCreator\" --project=\"${PROJECT}\""
        fi
      else
        echo "    ✔ Service Account impersonation already configured for ${CURRENT_USER}."
      fi
    else
      echo "    Skipped SA impersonation check (instance might not be fully applied yet)."
    fi

    echo ""
    echo "================================================================================"
    echo " SUCCESS: Connected to '${INSTANCE}'"
    echo " Workspace directory: ${WORKSPACE_DIR}"
    echo ""
    echo " Next Steps:"
    echo "   1. cd ${WORKSPACE_DIR}"
    echo "   2. Edit terraform.tfvars (if needed)"
    echo "   3. terraform apply"
    echo "================================================================================"
    echo ""

  # ==============================================================================
  # ACTION: PUSH-CONFIG
  # ==============================================================================
  elif [[ "$ACTION" == "push-config" ]]; then
    local TFVARS_FILE="$WORKSPACE_DIR/terraform.tfvars"
    if [[ ! -f "$TFVARS_FILE" ]]; then
      echo "Error: Local configuration '$TFVARS_FILE' not found."
      echo "Have you run '$0 connect --instance $INSTANCE' first?"
      return 1
    fi

    echo "==> Pushing local terraform.tfvars to Secret Manager ($SECRET_NAME)..."
    if ! gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" &>/dev/null; then
      echo "Error: Secret '$SECRET_NAME' does not exist in project '$PROJECT'."
      echo "Please ensure the testbed secret has been initialized by an administrator."
      return 1
    fi

    if [[ -t 0 ]]; then
      local confirm
      read -p "Are you sure you want to push your local terraform.tfvars to the shared secret '$SECRET_NAME'? [y/N]: " confirm
      if [[ ! "$confirm" =~ ^[yY](es)?$ ]]; then
        echo "Push cancelled."
        return 0
      fi
    fi

    gcloud secrets versions add "$SECRET_NAME" \
      --data-file="$TFVARS_FILE" \
      --project="$PROJECT"
    echo "==> Secret successfully updated in GCP Secret Manager!"

  else
    echo "Error: Unknown command '$ACTION'"
    echo ""
    print_usage
    return 1
  fi
}

main "$@"
