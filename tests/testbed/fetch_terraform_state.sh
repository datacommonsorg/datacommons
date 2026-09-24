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
  --force             Skip interactive confirmation prompts

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
     terraform apply

  3. Push your updated configuration back to the team secret:
     $0 push-config --instance testbed-1

  4. List all active testbeds:
     $0 list
HELP
}

log_error() {
  echo "Error: $1" >&2
  shift
  for line in "$@"; do
    echo "  $line" >&2
  done
}

# Ensure dependencies exist
check_dependencies() {
  local missing=0

  if ! command -v gcloud &>/dev/null; then
    log_error "'gcloud' CLI is not installed or not in PATH." \
              "Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
    missing=1
  fi

  if ! command -v terraform &>/dev/null; then
    log_error "'terraform' CLI is not installed or not in PATH." \
              "Install Terraform: https://developer.hashicorp.com/terraform/install"
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
    log_error "--instance <name> is required in non-interactive mode."
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
    log_error "Instance name cannot be empty."
    return 1
  fi

  echo "==> Selected instance: '$INSTANCE'"
  echo ""
  return 0
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

# Check and configure Spanner database permissions for CLI database setup
check_spanner_permissions() {
  local ws_dir="$1"
  local project="$2"

  local current_user
  current_user=$(gcloud config get-value account 2>/dev/null || true)
  local spanner_instance
  spanner_instance=$(cd "$ws_dir" && terraform output -raw spanner_instance_id 2>/dev/null || true)

  if [[ -n "$current_user" && -n "$spanner_instance" ]]; then
    echo "    Spanner Instance: ${spanner_instance}"

    local roles=("roles/spanner.databaseAdmin" "roles/spanner.databaseUser")
    for role in "${roles[@]}"; do
      local has_role
      has_role=$(gcloud spanner instances get-iam-policy "$spanner_instance" \
        --project="$project" \
        --filter="bindings.role=${role} AND bindings.members=user:${current_user}" \
        --format="value(bindings.role)" 2>/dev/null || true)

      if [[ -z "$has_role" ]]; then
        echo "    Granting '${role}' to user:${current_user} on ${spanner_instance}..."
        if gcloud spanner instances add-iam-policy-binding "$spanner_instance" \
             --member="user:${current_user}" \
             --role="${role}" \
             --project="$project" --quiet &>/dev/null; then
          echo "    ✔ Successfully granted ${role}."
        else
          echo "    Notice: Could not automatically grant ${role} (insufficient IAM admin rights)."
          echo "    To run 'datacommons admin init-db' or 'migrate-db', ask a project admin to run:"
          echo "      gcloud spanner instances add-iam-policy-binding \"${spanner_instance}\" --member=\"user:${current_user}\" --role=\"${role}\" --project=\"${project}\""
        fi
      else
        echo "    ✔ Spanner permission ${role} already configured for ${current_user}."
      fi
    done
  else
    echo "    Skipped Spanner permission check (instance might not be fully applied or enabled yet)."
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
    log_error "Unknown command '$ACTION'"
    print_usage
    return 1
  fi

  INSTANCE=""
  PROJECT="$DEFAULT_PROJECT"
  MODULES_SOURCE="local"
  FORCE=0

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
      --force)
        FORCE=1
        shift
        ;;
      --help|-h)
        print_usage
        return 0
        ;;
      *)
        log_error "Unknown option: $1"
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
    local tfvars="$WORKSPACE_DIR/terraform.tfvars"
    local should_fetch=1

    if [[ -f "$tfvars" && $FORCE -eq 0 ]]; then
      if [[ -t 0 ]]; then
        echo "    Notice: Local terraform.tfvars already exists in '${INSTANCE}'."
        read -p "    Overwrite with Secret Manager baseline? [y/N]: " overwrite_confirm
        if [[ ! "$overwrite_confirm" =~ ^[yY](es)?$ ]]; then
          echo "    Preserving local terraform.tfvars."
          should_fetch=0
        fi
      else
        echo "    Preserving existing local terraform.tfvars."
        should_fetch=0
      fi
    elif [[ -f "$tfvars" && $FORCE -eq 1 ]]; then
      echo "    --force specified: Overwriting local terraform.tfvars with Secret Manager baseline."
    fi

    if [[ $should_fetch -eq 1 ]]; then
      local tmp_tfvars="$WORKSPACE_DIR/terraform.tfvars.tmp"

      if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" &>/dev/null; then
        if gcloud secrets versions access latest \
            --secret="$SECRET_NAME" \
            --project="$PROJECT" > "$tmp_tfvars" && [[ -s "$tmp_tfvars" ]]; then
          [[ -f "$tfvars" ]] && cp "$tfvars" "$tfvars.bak"
          mv "$tmp_tfvars" "$tfvars"
          echo "    Successfully fetched terraform.tfvars from Secret Manager."
        else
          rm -f "$tmp_tfvars"
          log_error "Failed to fetch valid configuration from Secret Manager ('$SECRET_NAME')." \
                    "Please check your GCP credentials ('gcloud auth login') and secret permissions."
          return 1
        fi
      else
        echo "    Warning: Secret '$SECRET_NAME' does not exist in Secret Manager."
        if [[ ! -f "$tfvars" ]]; then
          echo "    Creating new boilerplate terraform.tfvars for '${INSTANCE}'..."
          cat <<TFVARS > "$tfvars"
project_id    = "${PROJECT}"
instance_name = "${INSTANCE}"
region        = "us-central1"
TFVARS
        fi
      fi
    fi

    echo "==> [3/5] Syncing Terraform scaffolding (${MODULES_SOURCE})..."
    if [[ "$MODULES_SOURCE" == "local" ]]; then
      cp "${INFRA_DCP_DIR}"/*.tf "$WORKSPACE_DIR/"
      ln -sfn "${INFRA_DCP_DIR}/modules" "$WORKSPACE_DIR/modules"
    else
      # Module source is a Git tag/ref
      local base_url="https://raw.githubusercontent.com/datacommonsorg/datacommons/${MODULES_SOURCE}/infra/dcp"
      echo "    Downloading root Terraform files from Git tag '${MODULES_SOURCE}'..."
      for f in variables.tf main.tf outputs.tf; do
        if ! curl -sSfL "${base_url}/${f}" -o "$WORKSPACE_DIR/${f}"; then
          log_error "Failed to download '${f}' from Git tag '${MODULES_SOURCE}'." \
                    "Please verify the tag exists at: https://github.com/datacommonsorg/datacommons/tags"
          return 1
        fi
      done

      rm -rf "$WORKSPACE_DIR/modules"

      local git_source="git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref=${MODULES_SOURCE}"
      python3 -c '
import sys, re
path, src = sys.argv[1], sys.argv[2]
with open(path, "r") as f:
    txt = f.read()
updated = re.sub(r"(?m)^\s*source\s*=\s*[\x22\x27]\./modules/stack[\x22\x27]", f"  source = \"{src}\"", txt)
with open(path, "w") as f:
    f.write(updated)
' "$WORKSPACE_DIR/main.tf" "$git_source"
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

    echo "==> [5/5] Checking Service Account impersonation & Spanner permissions..."
    check_sa_impersonation "$WORKSPACE_DIR" "$PROJECT"
    check_spanner_permissions "$WORKSPACE_DIR" "$PROJECT"

    echo ""
    echo "================================================================================"
    echo " SUCCESS: Connected to '${INSTANCE}'"
    echo " Workspace directory: ${WORKSPACE_DIR}"
    echo " Module source:       ${MODULES_SOURCE}"
    echo ""
    echo " Next Steps:"
    echo "   1. cd ${WORKSPACE_DIR}"
    echo "   2. Edit terraform.tfvars (if needed)"
    echo "   3. terraform apply"
    echo "================================================================================"
  # ==============================================================================
  # ACTION: PUSH-CONFIG
  # ==============================================================================
  elif [[ "$ACTION" == "push-config" ]]; then
    local TFVARS_FILE="$WORKSPACE_DIR/terraform.tfvars"
    if [[ ! -f "$TFVARS_FILE" ]]; then
      log_error "Local configuration '$TFVARS_FILE' not found." \
                "Have you run '$0 connect --instance $INSTANCE' first?"
      return 1
    fi

    if [[ ! -s "$TFVARS_FILE" ]]; then
      log_error "Local configuration '$TFVARS_FILE' is empty. Refusing to push."
      return 1
    fi

    echo "==> Pushing local terraform.tfvars to Secret Manager ($SECRET_NAME)..."
    if ! gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" &>/dev/null; then
      log_error "Secret '$SECRET_NAME' does not exist in project '$PROJECT'." \
                "Please ensure the testbed secret has been initialized by an administrator."
      return 1
    fi

    if [[ $FORCE -eq 0 && -t 0 ]]; then
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
    log_error "Unknown command '$ACTION'"
    print_usage
    return 1
  fi
}

main "$@"
