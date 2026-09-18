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
# Enables rapid connection, configuration synchronization, module source switching,
# and IAM impersonation for shared developer testbeds in Google Cloud Platform.
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
  connect       Connect to a testbed (pulls baseline config, wires backend, inits Terraform, checks IAM)
  push-config   Save and push local terraform.tfvars back to GCP Secret Manager
  list          List available testbeds in the project

Global Options:
  --instance <name>     Instance name (e.g. testbed-1, testbed-2)
  --project <id>        GCP Project ID (default: ${DEFAULT_PROJECT})
  --yes, -y             Non-interactive mode (automatically confirm prompts)

Options for 'connect':
  --terraform-modules-source <local|tag>
                        Where Terraform modules (including workflow.yaml) come from:
                        • local: Dev mode. Symlinks to local infra/dcp/modules (default).
                        • <tag>: Git tag (e.g. v1.1.5). Loads official modules from GitHub.
                        (See available tags: https://github.com/datacommonsorg/datacommons/tags)

Developer Workflow:
  1. Connect to an instance:
     $0 connect --instance testbed-1 --terraform-modules-source v1.1.5
     # OR to test local module / workflow.yaml edits:
     $0 connect --instance testbed-1 --terraform-modules-source local

  2. Navigate to your workspace, edit terraform.tfvars, and apply:
     cd tests/testbed/workspaces/testbed-1
     terraform plan
     terraform apply

  3. Push your updated configuration back to the team secret (optional):
     $0 push-config --instance testbed-1

  4. List all active testbeds:
     $0 list
HELP
}

# Ensure dependencies exist
check_dependencies() {
  local missing=0

  if ! command -v gcloud &>/dev/null; then
    echo "Error: 'gcloud' CLI is not installed or not in PATH." >&2
    echo "  Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install" >&2
    missing=1
  fi

  if ! command -v terraform &>/dev/null; then
    echo "Error: 'terraform' CLI is not installed or not in PATH." >&2
    echo "  Install Terraform: https://developer.hashicorp.com/terraform/install" >&2
    missing=1
  fi

  if [[ $missing -eq 1 ]]; then
    return 1
  fi

  return 0
}

# Interactive prompt to select or enter an instance if --instance was omitted
prompt_instance_if_missing() {
  if [[ -n "$INSTANCE" ]]; then
    return 0
  fi

  # Auto-infer instance name if running inside a workspace folder (e.g. tests/testbed/workspaces/testbed-1)
  local current_dir
  current_dir="$(pwd)"
  if [[ "$current_dir" == *"/workspaces/"* ]]; then
    INSTANCE="$(basename "$current_dir")"
    echo "==> Auto-detected instance '$INSTANCE' from current directory."
    return 0
  fi

  # If not running interactively, error out
  if [[ ! -t 0 ]]; then
    echo "Error: --instance <name> is required in non-interactive mode." >&2
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
      INSTANCE="$choice"
    fi
  else
    read -p "No existing testbeds found. Enter instance name to connect: " INSTANCE
  fi

  if [[ -z "$INSTANCE" ]]; then
    echo "Error: Instance name cannot be empty." >&2
    return 1
  fi

  echo "==> Selected instance: '$INSTANCE'"
  echo ""
  return 0
}

# Resolve git ref: check locally, fetch tags from remotes if missing
resolve_git_ref() {
  local ref="$1"
  if git rev-parse --verify "${ref}^{commit}" &>/dev/null; then
    return 0
  fi

  echo "==> Ref '${ref}' not found locally. Fetching tags from remotes..." >&2
  git fetch origin --tags --quiet 2>/dev/null || true
  git fetch upstream --tags --quiet 2>/dev/null || true

  if git rev-parse --verify "${ref}^{commit}" &>/dev/null; then
    return 0
  fi

  echo "Error: Cannot resolve Git reference '${ref}' locally or from remotes." >&2
  echo "See available tags at: https://github.com/datacommonsorg/datacommons/tags" >&2
  return 1
}

# Check and configure service account impersonation for CLI commands
check_sa_impersonation() {
  local ws_dir="$1"
  local project="$2"

  local current_user
  current_user=$(gcloud config get-value account 2>/dev/null || true)
  local workflow_sa
  workflow_sa=$(cd "$ws_dir" && terraform output -raw ingestion_workflow_service_account_email 2>/dev/null || true)

  if [[ -n "$current_user" && -n "$workflow_sa" ]]; then
    echo "    Authenticated user: ${current_user}"
    echo "    Workflow Service Account: ${workflow_sa}"

    local has_role
    has_role=$(gcloud iam service-accounts get-iam-policy "$workflow_sa" \
      --project="$project" \
      --filter="bindings.role=roles/iam.serviceAccountTokenCreator AND bindings.members=user:${current_user}" \
      --format="value(bindings.role)" 2>/dev/null || true)

    if [[ -z "$has_role" ]]; then
      echo "    Granting 'roles/iam.serviceAccountTokenCreator' to user:${current_user} on ${workflow_sa}..."
      if gcloud iam service-accounts add-iam-policy-binding "$workflow_sa" \
           --member="user:${current_user}" \
           --role="roles/iam.serviceAccountTokenCreator" \
           --project="$project" --quiet &>/dev/null; then
        echo "    ✔ Successfully configured Service Account impersonation."
      else
        echo "    Notice: Could not automatically grant TokenCreator permission (insufficient IAM admin rights)."
        echo "    If you plan to run ingestion CLI commands, ask a project admin to run:"
        echo "      gcloud iam service-accounts add-iam-policy-binding \"${workflow_sa}\" --member=\"user:${current_user}\" --role=\"roles/iam.serviceAccountTokenCreator\" --project=\"${project}\""
      fi
    else
      echo "    ✔ Service Account impersonation already configured for ${current_user}."
    fi
  else
    echo "    Skipped SA impersonation check (instance might not be fully applied yet)."
  fi
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
    echo "Error: Unknown command '$ACTION'" >&2
    echo "" >&2
    print_usage
    return 1
  fi

  INSTANCE=""
  PROJECT="$DEFAULT_PROJECT"
  MODULES_SOURCE="local"
  YES_FLAG=0

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
      --terraform-modules-source)
        MODULES_SOURCE="$2"
        shift 2
        ;;
      --yes|-y)
        YES_FLAG=1
        shift
        ;;
      --help|-h)
        print_usage
        return 0
        ;;
      *)
        echo "Error: Unknown option: $1" >&2
        print_usage
        return 1
        ;;
    esac
  done

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
    local secrets
    secrets=$(gcloud secrets list --project="${PROJECT}" --format="value(name)" 2>/dev/null || true)

    local found=0
    local options=()
    for s in $secrets; do
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
    if [[ -t 0 && $YES_FLAG -eq 0 ]]; then
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

    echo "==> [2/5] Synchronizing configuration from Secret Manager ($SECRET_NAME)..."
    local fetch_secret=1
    local local_tfvars="$WORKSPACE_DIR/terraform.tfvars"

    if [[ -f "$local_tfvars" ]]; then
      if [[ $YES_FLAG -eq 0 && -t 0 ]]; then
        echo "    Notice: Local terraform.tfvars already exists in '${INSTANCE}'."
        read -p "    Overwrite with Secret Manager baseline? [y/N]: " overwrite_confirm
        if [[ ! "$overwrite_confirm" =~ ^[yY](es)?$ ]]; then
          echo "    Preserving local terraform.tfvars."
          fetch_secret=0
        fi
      else
        # In non-interactive mode, preserve existing local file to avoid accidental clobbering
        echo "    Preserving existing local terraform.tfvars."
        fetch_secret=0
      fi
    fi

    if [[ $fetch_secret -eq 1 ]]; then
      local secret_output
      if ! secret_output=$(gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" 2>&1); then
        if [[ "$secret_output" =~ "NOT_FOUND" || "$secret_output" =~ "not found" ]]; then
          echo "    Notice: Secret '$SECRET_NAME' does not exist in Secret Manager."
          if [[ ! -f "$local_tfvars" ]]; then
            echo "    Creating new boilerplate terraform.tfvars for '${INSTANCE}'..."
            cat <<TFVARS > "$local_tfvars"
project_id    = "${PROJECT}"
instance_name = "${INSTANCE}"
region        = "us-central1"
TFVARS
          fi
        else
          echo "Error: Failed to access Secret Manager for '$SECRET_NAME':" >&2
          echo "$secret_output" >&2
          return 1
        fi
      else
        if [[ -f "$local_tfvars" ]]; then
          cp "$local_tfvars" "$local_tfvars.bak"
        fi
        gcloud secrets versions access latest \
          --secret="$SECRET_NAME" \
          --project="$PROJECT" > "$local_tfvars.tmp"
        mv "$local_tfvars.tmp" "$local_tfvars"
        echo "    Successfully fetched terraform.tfvars from Secret Manager."
      fi
    fi

    echo "==> [3/5] Configuring Terraform module source: '${MODULES_SOURCE}'..."
    if [[ "$MODULES_SOURCE" == "local" ]]; then
      cp "${INFRA_DCP_DIR}"/*.tf "$WORKSPACE_DIR/"
      ln -sfn "${INFRA_DCP_DIR}/modules" "$WORKSPACE_DIR/modules"

      python3 -c "
import sys, re
path = sys.argv[1]
with open(path, 'r') as f:
    content = f.read()
updated = re.sub(r'source\s*=\s*\"[^\"]+\"', 'source = \"./modules/stack\"', content, count=1)
with open(path, 'w') as f:
    f.write(updated)
" "$WORKSPACE_DIR/main.tf"

      # Check for dirty working tree in modules
      local dirty_files
      dirty_files=$(git status --porcelain "${INFRA_DCP_DIR}/modules" 2>/dev/null || true)
      if [[ -n "$dirty_files" ]]; then
        echo "    Notice: Uncommitted changes detected in local infra/dcp/modules."
      fi

    else
      # Module source is a Git tag/ref
      local target_ref="$MODULES_SOURCE"
      echo "    Resolving Git reference '${target_ref}'..."
      if ! resolve_git_ref "$target_ref"; then
        return 1
      fi

      echo "    Extracting root Terraform definition files from Git ref '${target_ref}'..."
      for f in variables.tf main.tf outputs.tf; do
        if ! git show "${target_ref}:infra/dcp/${f}" > "$WORKSPACE_DIR/${f}.tmp" 2>/dev/null; then
          echo "Error: Failed to extract ${f} from Git ref '${target_ref}'" >&2
          rm -f "$WORKSPACE_DIR/${f}.tmp"
          return 1
        fi
        mv "$WORKSPACE_DIR/${f}.tmp" "$WORKSPACE_DIR/${f}"
      done

      rm -rf "$WORKSPACE_DIR/modules"

      local git_source="source = \"git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref=${target_ref}\""
      python3 -c "
import sys, re
path = sys.argv[1]
git_src = sys.argv[2]
with open(path, 'r') as f:
    content = f.read()
updated = re.sub(r'source\s*=\s*\"[^\"]+\"', git_src, content, count=1)
with open(path, 'w') as f:
    f.write(updated)
" "$WORKSPACE_DIR/main.tf" "$git_source"
    fi

    # Clean module cache so Terraform downloads/updates sources cleanly
    rm -rf "$WORKSPACE_DIR/.terraform/modules"

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
      echo "    Running terraform init -upgrade..."
      terraform init -upgrade
    )

    echo "==> [5/5] Checking Service Account impersonation permissions..."
    check_sa_impersonation "$WORKSPACE_DIR" "$PROJECT"

    echo ""
    echo "================================================================================"
    echo " SUCCESS: Connected to '${INSTANCE}'"
    echo " Workspace directory: ${WORKSPACE_DIR}"
    echo " Module source:       ${MODULES_SOURCE}"
    echo ""
    echo " Next Steps:"
    echo "   1. cd ${WORKSPACE_DIR}"
    echo "   2. Edit terraform.tfvars as needed"
    echo "   3. terraform plan"
    echo "   4. terraform apply"
    echo "================================================================================"
    echo ""
    return 0
  fi

  # ==============================================================================
  # ACTION: PUSH-CONFIG
  # ==============================================================================
  if [[ "$ACTION" == "push-config" ]]; then
    local tfvars_file="$WORKSPACE_DIR/terraform.tfvars"
    if [[ ! -f "$tfvars_file" ]]; then
      echo "Error: Local configuration '$tfvars_file' not found." >&2
      echo "Have you run '$0 connect --instance $INSTANCE' first?" >&2
      return 1
    fi

    if [[ ! -s "$tfvars_file" ]]; then
      echo "Error: Local configuration '$tfvars_file' is empty. Refusing to push." >&2
      return 1
    fi

    echo "==> Target secret: $SECRET_NAME (project: $PROJECT)"
    if ! gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" &>/dev/null; then
      echo "Error: Secret '$SECRET_NAME' does not exist in project '$PROJECT'." >&2
      echo "Please ensure the testbed secret has been initialized by an administrator." >&2
      return 1
    fi

    if [[ $YES_FLAG -eq 0 && -t 0 ]]; then
      local confirm
      read -p "Are you sure you want to push your local terraform.tfvars to the shared secret '$SECRET_NAME'? [y/N]: " confirm
      if [[ ! "$confirm" =~ ^[yY](es)?$ ]]; then
        echo "Push cancelled."
        return 0
      fi
    fi

    gcloud secrets versions add "$SECRET_NAME" \
      --data-file="$tfvars_file" \
      --project="$PROJECT"
    echo "==> Secret successfully updated in GCP Secret Manager!"
    return 0
  fi

  echo "Error: Unknown action '$ACTION'" >&2
  print_usage
  return 1
}

main "$@"
