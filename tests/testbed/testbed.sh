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
# container version overrides, and IAM impersonation for shared developer testbeds.
# ==============================================================================

set -eo pipefail

# Find repository root and testbed directories
TESTBED_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${TESTBED_DIR}/../.." && pwd)"
WORKSPACES_ROOT="${TESTBED_DIR}/workspaces"
INFRA_DCP_DIR="${REPO_ROOT}/infra/dcp"
OVERRIDES_TEMPLATE="${TESTBED_DIR}/testbed_overrides.tfvars.template"

# Default project if not specified
DEFAULT_PROJECT="datcom-dcp"

print_usage() {
  cat <<HELP
Data Commons Platform - Developer Testbed CLI

Usage:
  $0 <command> [options]

Commands:
  connect       Connect/attach to an existing testbed (pulls baseline secret, inits Terraform, checks IAM)
  configure     Mutate workspace configuration (switch module sources, bump versions, set image overrides, plan, apply)
  push-config   Explicitly save and push local terraform.tfvars back to GCP Secret Manager
  list          List available testbeds in the project

Global Options:
  --instance <name>     Instance name (e.g. testbed-1, testbed-2)
  --project <id>        GCP Project ID (default: ${DEFAULT_PROJECT})
  --yes, -y             Non-interactive mode (automatically confirm prompts)

Options for 'configure':
  --terraform-source <git|local>   Where Terraform modules come from:
                                   • git: Hermetic mode. Pins module source to GitHub tag/ref (no local file leaks).
                                   • local: Dev mode. Symlinks modules to local infra/dcp/modules.
  --terraform-ref <ref>            Git tag/branch/commit when --terraform-source git is used (default: v<dcp_version>)
  --dcp-version <version>          Sets dcp_version in terraform.tfvars (updates baseline tag for all services)
  --services-image <image-uri>     Sets datacommons_services_image in terraform.tfvars
  --clear-image-overrides          Comments out all custom image overrides, resetting services to dcp_version
  --plan                           Generate Terraform plan (default: true)
  --no-plan                        Skip generating Terraform plan
  --apply                          Execute terraform apply after planning
  --push-config                    Persist updated terraform.tfvars to Secret Manager after apply (default: false)

Common Workflows:
  1. Attach to an existing testbed without modifying anything:
     $0 connect --instance testbed-1

  2. Test a custom container image against a clean release tag:
     $0 configure --instance testbed-1 \\
       --terraform-source git --terraform-ref v1.1.5 \\
       --dcp-version 1.1.5 \\
       --services-image gcr.io/datcom-website-dev/datacommons-services:my-tag \\
       --apply

  3. Test local Terraform module / workflow.yaml edits:
     $0 configure --instance testbed-1 --terraform-source local --apply

  4. Reset all custom container overrides back to the baseline release:
     $0 configure --instance testbed-1 --clear-image-overrides --apply

  5. Deliberately promote local settings to the team's shared secret:
     $0 push-config --instance testbed-1
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

  if ! command -v python3 &>/dev/null; then
    echo "Error: 'python3' is not installed or not in PATH." >&2
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

# Resolve git ref safely: check locally, fetch tags from origin/upstream if missing
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

  echo "Error: Cannot resolve Git reference '${ref}' locally or from git remotes." >&2
  return 1
}

# Python helper to read a variable from terraform.tfvars
get_tfvar() {
  local key="$1"
  local file="$2"
  if [[ ! -f "$file" ]]; then
    echo ""
    return 0
  fi
  python3 -c "
import sys, re
key = sys.argv[1]
with open(sys.argv[2], 'r') as f:
    text = f.read()
m = re.search(rf'^\s*{re.escape(key)}\s*=\s*\"([^\"]*)\"', text, re.MULTILINE)
if m:
    print(m.group(1))
" "$key" "$file"
}

# Python helper to update or uncomment a variable in terraform.tfvars
set_tfvar() {
  local key="$1"
  local val="$2"
  local file="$3"
  python3 -c "
import sys, re
key = sys.argv[1]
val = sys.argv[2]
path = sys.argv[3]
with open(path, 'r') as f:
    content = f.read()

pattern = rf'^\s*#?\s*{re.escape(key)}\s*=.*$'
replacement = f'{key} = \"{val}\"'
if re.search(pattern, content, re.MULTILINE):
    updated = re.sub(pattern, lambda m: replacement, content, count=1, flags=re.MULTILINE)
else:
    updated = content.rstrip() + f'\n{replacement}\n'

with open(path, 'w') as f:
    f.write(updated)
" "$key" "$val" "$file"
}

# Python helper to comment out a variable in terraform.tfvars
comment_out_tfvar() {
  local key="$1"
  local file="$2"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  python3 -c "
import sys, re
key = sys.argv[1]
path = sys.argv[2]
with open(path, 'r') as f:
    content = f.read()

pattern = rf'^(\s*)({re.escape(key)}\s*=.*)$'
updated = re.sub(pattern, r'\1# \2', content, flags=re.MULTILINE)
with open(path, 'w') as f:
    f.write(updated)
" "$key" "$file"
}

# Detect current active module source in a workspace
detect_active_source() {
  local ws_dir="$1"
  local main_tf="$ws_dir/main.tf"
  if [[ ! -f "$main_tf" ]]; then
    echo "Unknown"
    return
  fi

  if grep -q 'source = "./modules/stack"' "$main_tf"; then
    echo "local"
  else
    local git_ref
    git_ref=$(python3 -c "
import sys, re
with open(sys.argv[1]) as f:
    content = f.read()
m = re.search(r'source\s*=\s*\"git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack\?ref=([^\"]+)\"', content)
if m:
    print(m.group(1))
" "$main_tf")
    if [[ -n "$git_ref" ]]; then
      echo "git ($git_ref)"
    else
      echo "custom"
    fi
  fi
}

# Check and grant TokenCreator IAM permission
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
  fi
}

main() {
  local ACTION="$1"
  if [[ "$ACTION" == "--help" || "$ACTION" == "-h" ]]; then
    print_usage
    return 0
  elif [[ "$ACTION" == "connect" || "$ACTION" == "configure" || "$ACTION" == "push-config" || "$ACTION" == "list" ]]; then
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
  YES_FLAG=0

  # Options for configure
  TF_SOURCE=""
  TF_REF=""
  DCP_VERSION=""
  SERVICES_IMAGE=""
  CLEAR_IMAGE_OVERRIDES=0
  RUN_PLAN=1
  RUN_APPLY=0
  DO_PUSH_CONFIG=0

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
      --yes|-y)
        YES_FLAG=1
        shift
        ;;
      --terraform-source)
        TF_SOURCE="$2"
        shift 2
        ;;
      --terraform-ref)
        TF_REF="$2"
        shift 2
        ;;
      --dcp-version)
        DCP_VERSION="$2"
        shift 2
        ;;
      --services-image)
        SERVICES_IMAGE="$2"
        shift 2
        ;;
      --clear-image-overrides)
        CLEAR_IMAGE_OVERRIDES=1
        shift
        ;;
      --plan)
        RUN_PLAN=1
        shift
        ;;
      --no-plan)
        RUN_PLAN=0
        shift
        ;;
      --apply)
        RUN_APPLY=1
        shift
        ;;
      --push-config)
        DO_PUSH_CONFIG=1
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

  # Helper function to perform baseline connect/attach
  do_connect() {
    echo "==> [1/5] Connecting to testbed '${INSTANCE}' in project '${PROJECT}'..."
    mkdir -p "$WORKSPACE_DIR"

    echo "==> [2/5] Pulling configuration from Secret Manager ($SECRET_NAME)..."
    local secret_output
    if ! secret_output=$(gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" 2>&1); then
      if [[ "$secret_output" =~ "NOT_FOUND" || "$secret_output" =~ "not found" ]]; then
        echo "    Notice: Secret '$SECRET_NAME' does not exist in Secret Manager."
        if [[ ! -f "$WORKSPACE_DIR/terraform.tfvars" ]]; then
          echo "    Seeding initial terraform.tfvars with project overrides..."
          cat <<TFVARS > "$WORKSPACE_DIR/terraform.tfvars"
project_id    = "${PROJECT}"
instance_name = "${INSTANCE}"
region        = "us-central1"

TFVARS
          if [[ -f "$OVERRIDES_TEMPLATE" ]]; then
            cat "$OVERRIDES_TEMPLATE" >> "$WORKSPACE_DIR/terraform.tfvars"
          fi
        fi
      else
        echo "Error: Failed to access Secret Manager for '$SECRET_NAME':" >&2
        echo "$secret_output" >&2
        return 1
      fi
    else
      if [[ -f "$WORKSPACE_DIR/terraform.tfvars" ]]; then
        cp "$WORKSPACE_DIR/terraform.tfvars" "$WORKSPACE_DIR/terraform.tfvars.bak"
      fi
      gcloud secrets versions access latest \
        --secret="$SECRET_NAME" \
        --project="$PROJECT" > "$WORKSPACE_DIR/terraform.tfvars.tmp"
      mv "$WORKSPACE_DIR/terraform.tfvars.tmp" "$WORKSPACE_DIR/terraform.tfvars"
      echo "    Successfully fetched terraform.tfvars from Secret Manager."
    fi

    # Sync base Terraform files and default local modules symlink if not already configured
    echo "==> [3/5] Syncing Terraform scaffolding..."
    cp "${INFRA_DCP_DIR}"/*.tf "$WORKSPACE_DIR/"
    if [[ ! -L "$WORKSPACE_DIR/modules" && ! -d "$WORKSPACE_DIR/modules" ]]; then
      ln -sfn "${INFRA_DCP_DIR}/modules" "$WORKSPACE_DIR/modules"
    fi

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

    echo "==> [5/5] Checking Service Account impersonation permissions..."
    check_sa_impersonation "$WORKSPACE_DIR" "$PROJECT"
  }

  # ==============================================================================
  # ACTION: CONNECT (Read & Attach Only)
  # ==============================================================================
  if [[ "$ACTION" == "connect" ]]; then
    do_connect

    echo ""
    echo "================================================================================"
    echo " SUCCESS: Connected to '${INSTANCE}'"
    echo " Workspace directory: ${WORKSPACE_DIR}"
    echo ""
    echo " Next Steps:"
    echo "   1. Configure version or custom container overrides:"
    echo "      $0 configure --instance ${INSTANCE} [options]"
    echo "   2. Or enter workspace to run terraform directly:"
    echo "      cd ${WORKSPACE_DIR}"
    echo "================================================================================"
    echo ""
    return 0
  fi

  # ==============================================================================
  # ACTION: CONFIGURE (Mutate, Plan & Rollout)
  # ==============================================================================
  if [[ "$ACTION" == "configure" ]]; then
    # Auto-connect if workspace does not exist yet
    if [[ ! -f "$WORKSPACE_DIR/backend.tf" || ! -f "$WORKSPACE_DIR/terraform.tfvars" ]]; then
      echo "==> Workspace '${WORKSPACE_DIR}' not initialized yet. Auto-connecting..."
      do_connect
      echo ""
    fi

    local NEED_UPGRADE=0

    # 1. Handle Module Source
    if [[ -n "$TF_SOURCE" ]]; then
      if [[ "$TF_SOURCE" == "git" ]]; then
        # Determine target ref
        local target_ref="$TF_REF"
        if [[ -z "$target_ref" ]]; then
          if [[ -n "$DCP_VERSION" ]]; then
            target_ref="v${DCP_VERSION}"
          else
            local cur_dcp_ver
            cur_dcp_ver=$(get_tfvar "dcp_version" "$WORKSPACE_DIR/terraform.tfvars")
            if [[ -n "$cur_dcp_ver" ]]; then
              target_ref="v${cur_dcp_ver}"
            else
              target_ref="main"
            fi
          fi
        fi

        echo "==> Resolving Git ref '${target_ref}'..."
        if ! resolve_git_ref "$target_ref"; then
          return 1
        fi

        echo "==> Configuring hermetic Git module source (ref: ${target_ref})..."
        # Extract root .tf files from git ref
        for f in variables.tf main.tf outputs.tf; do
          if ! git show "${target_ref}:infra/dcp/${f}" > "$WORKSPACE_DIR/${f}.tmp" 2>/dev/null; then
            echo "Error: Failed to extract ${f} from git ref '${target_ref}'" >&2
            rm -f "$WORKSPACE_DIR/${f}.tmp"
            return 1
          fi
          mv "$WORKSPACE_DIR/${f}.tmp" "$WORKSPACE_DIR/${f}"
        done

        # Remove local modules symlink
        rm -rf "$WORKSPACE_DIR/modules"

        # Rewrite main.tf module source to GitHub
        python3 -c "
import sys, re
path = sys.argv[1]
ref = sys.argv[2]
with open(path, 'r') as f:
    content = f.read()

git_source = f'source = \"git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref={ref}\"'
updated = re.sub(r'source\s*=\s*\"[^\"]+\"', git_source, content, count=1)
with open(path, 'w') as f:
    f.write(updated)
" "$WORKSPACE_DIR/main.tf" "$target_ref"

        # Purge stale module cache
        rm -rf "$WORKSPACE_DIR/.terraform/modules"
        NEED_UPGRADE=1

      elif [[ "$TF_SOURCE" == "local" ]]; then
        echo "==> Configuring local module source (symlink to infra/dcp/modules)..."
        cp "${INFRA_DCP_DIR}"/*.tf "$WORKSPACE_DIR/"
        ln -sfn "${INFRA_DCP_DIR}/modules" "$WORKSPACE_DIR/modules"

        python3 -c "
import sys, re
path = sys.argv[1]
with open(path, 'r') as f:
    content = f.read()

local_source = 'source = \"./modules/stack\"'
updated = re.sub(r'source\s*=\s*\"[^\"]+\"', local_source, content, count=1)
with open(path, 'w') as f:
    f.write(updated)
" "$WORKSPACE_DIR/main.tf"

        # Purge stale module cache
        rm -rf "$WORKSPACE_DIR/.terraform/modules"
        NEED_UPGRADE=1

      else
        echo "Error: Invalid --terraform-source: '${TF_SOURCE}'. Must be 'git' or 'local'." >&2
        return 1
      fi
    fi

    # 2. Update dcp_version in terraform.tfvars
    if [[ -n "$DCP_VERSION" ]]; then
      echo "==> Setting dcp_version = \"${DCP_VERSION}\"..."
      set_tfvar "dcp_version" "$DCP_VERSION" "$WORKSPACE_DIR/terraform.tfvars"
    fi

    # 3. Update datacommons_services_image override
    if [[ -n "$SERVICES_IMAGE" ]]; then
      echo "==> Setting datacommons_services_image = \"${SERVICES_IMAGE}\"..."
      set_tfvar "datacommons_services_image" "$SERVICES_IMAGE" "$WORKSPACE_DIR/terraform.tfvars"
    fi

    # 4. Clear image overrides
    if [[ $CLEAR_IMAGE_OVERRIDES -eq 1 ]]; then
      echo "==> Resetting granular container image overrides..."
      for key in datacommons_services_image ingestion_helper_service_image ingestion_preprocessing_job_image ingestion_postprocessing_job_image ingestion_dataflow_template_gcs_path; do
        comment_out_tfvar "$key" "$WORKSPACE_DIR/terraform.tfvars"
      done
    fi

    # 5. Display Structured Summary
    local active_src
    active_src=$(detect_active_source "$WORKSPACE_DIR")
    local cur_ver
    cur_ver=$(get_tfvar "dcp_version" "$WORKSPACE_DIR/terraform.tfvars")
    local cur_services_img
    cur_services_img=$(get_tfvar "datacommons_services_image" "$WORKSPACE_DIR/terraform.tfvars")

    echo ""
    echo "================================================================================"
    echo " Testbed Configuration: ${INSTANCE} (${PROJECT})"
    echo "================================================================================"
    echo " • Module Source:     ${active_src}"
    echo " • Baseline Version:  dcp_version = \"${cur_ver:-default}\""
    if [[ -n "$cur_services_img" ]]; then
      echo " • Services Image:    ${cur_services_img}"
    else
      echo " • Services Image:    (using baseline dcp_version)"
    fi

    if [[ "$active_src" == "local" ]]; then
      local dirty_files
      dirty_files=$(git status --porcelain "${INFRA_DCP_DIR}/modules" 2>/dev/null || true)
      if [[ -n "$dirty_files" ]]; then
        echo " ⚠️ Notice: Uncommitted changes detected in infra/dcp/modules."
        echo "    Running 'apply' will deploy your uncommitted local modifications."
      fi
    fi
    echo "================================================================================"
    echo ""

    # 6. Re-init Terraform if upgrade required
    if [[ $NEED_UPGRADE -eq 1 ]]; then
      (
        cd "$WORKSPACE_DIR"
        echo "==> Re-initializing Terraform with upgraded module source..."
        terraform init -upgrade
      )
    fi

    # 7. Terraform Plan
    if [[ $RUN_PLAN -eq 1 ]]; then
      (
        cd "$WORKSPACE_DIR"
        echo "==> Generating Terraform plan (tfplan)..."
        terraform plan -out=tfplan
      )
    fi

    # 8. Terraform Apply
    if [[ $RUN_APPLY -eq 1 ]]; then
      if [[ $YES_FLAG -eq 0 && -t 0 ]]; then
        echo ""
        local confirm
        read -p "Apply this plan to '${INSTANCE}' in project '${PROJECT}'? [y/N]: " confirm
        if [[ ! "$confirm" =~ ^[yY](es)?$ ]]; then
          echo "Apply cancelled."
          return 0
        fi
      fi

      (
        cd "$WORKSPACE_DIR"
        echo "==> Executing terraform apply..."
        terraform apply tfplan
      )
      echo ""
      echo "✔ Successfully applied configuration to '${INSTANCE}'."

      # 9. Push Config (only if explicitly set)
      if [[ $DO_PUSH_CONFIG -eq 1 ]]; then
        echo ""
        echo "==> Pushing updated terraform.tfvars to Secret Manager ($SECRET_NAME)..."
        gcloud secrets versions add "$SECRET_NAME" \
          --data-file="$WORKSPACE_DIR/terraform.tfvars" \
          --project="$PROJECT"
        echo "✔ Secret successfully updated in GCP Secret Manager!"
      fi
    fi

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
