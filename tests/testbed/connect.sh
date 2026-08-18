#!/usr/bin/env bash
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
  exit 1
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
    exit 1
  fi

  # Check for datacommons CLI (warning if not in PATH or uv)
  if ! command -v datacommons &>/dev/null && ! uv run datacommons --help &>/dev/null 2>&1; then
    echo "Notice: 'datacommons' CLI is not installed in PATH."
    echo "  To run ingestion/workflow CLI commands, install it via: pip install -e packages/datacommons-cli"
    echo "  (or execute via: uv run datacommons <command>)"
    echo ""
  fi
}

ACTION="$1"
if [[ "$ACTION" == "--help" || "$ACTION" == "-h" ]]; then
  print_usage
elif [[ "$ACTION" == "connect" || "$ACTION" == "push-config" || "$ACTION" == "list" ]]; then
  shift
elif [[ "$ACTION" == --* || -z "$ACTION" ]]; then
  ACTION="connect"
else
  echo "Error: Unknown command '$ACTION'"
  print_usage
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
      ;;
    *)
      echo "Error: Unknown option: $1"
      print_usage
      ;;
  esac
done

# Auto-infer instance name if running inside a workspace folder (e.g. tests/testbed/workspaces/testbed-1)
if [[ -z "$INSTANCE" ]]; then
  CURRENT_DIR="$(pwd)"
  if [[ "$CURRENT_DIR" == *"/workspaces/"* ]]; then
    INSTANCE="$(basename "$CURRENT_DIR")"
    echo "==> Auto-detected instance '$INSTANCE' from current directory."
  fi
fi

check_dependencies

# ==============================================================================
# ACTION: LIST
# ==============================================================================
if [[ "$ACTION" == "list" ]]; then
  echo "================================================================================"
  echo "DCP TESTBEDS in project: ${PROJECT}"
  echo "================================================================================"
  
  echo "Fetching registered testbed secrets from Secret Manager..."
  SECRETS=$(gcloud secrets list --project="${PROJECT}" --format="value(name)" 2>/dev/null || true)

  found=0
  options=()
  for s in $SECRETS; do
    secret_id=$(basename "$s")
    if [[ "$secret_id" =~ ^dcp-(.+)-tfvars$ ]]; then
      if [[ $found -eq 0 ]]; then
        printf "%-5s %-25s %-35s\n" "#" "INSTANCE NAME" "SECRET NAME"
        printf "%-5s %-25s %-35s\n" "--" "-------------" "-----------"
      fi
      inst_name="${BASH_REMATCH[1]}"
      options+=("$inst_name")
      found=$((found + 1))
      printf "%-5s %-25s %-35s\n" "$found" "$inst_name" "$secret_id"
    fi
  done

  if [[ $found -eq 0 ]]; then
    echo "No 'dcp-*-tfvars' secrets found in project '${PROJECT}'."
    exit 0
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
      exit 0
    fi
  else
    exit 0
  fi
fi

# Interactive prompt to select or enter an instance if --instance was omitted
prompt_instance_if_missing() {
  if [[ -n "$INSTANCE" ]]; then
    return
  fi

  # If not running interactively (e.g. CI/CD), error out
  if [[ ! -t 0 ]]; then
    echo "Error: --instance <name> is required in non-interactive mode."
    exit 1
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
    exit 1
  fi

  echo "==> Selected instance: '$INSTANCE'"
  echo ""
}

prompt_instance_if_missing

SECRET_NAME="dcp-${INSTANCE}-tfvars"
WORKSPACE_DIR="${WORKSPACES_ROOT}/${INSTANCE}"
STATE_BUCKET="tf-state-${INSTANCE}-${PROJECT}"

# ==============================================================================
# ACTION: CONNECT
# ==============================================================================
if [[ "$ACTION" == "connect" ]]; then
  echo "==> [1/5] Connecting to testbed '${INSTANCE}' in project '${PROJECT}'..."
  mkdir -p "$WORKSPACE_DIR"

  echo "==> [2/5] Pulling configuration from Secret Manager ($SECRET_NAME)..."
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

  echo "==> [3/5] Setting up remote GCS backend state..."
  cat <<BACKEND > "$WORKSPACE_DIR/backend.tf"
terraform {
  backend "gcs" {
    bucket = "${STATE_BUCKET}"
    prefix = "terraform/state/${INSTANCE}"
  }
}
BACKEND

  # Copy root terraform definition files into workspace and symlink modules
  echo "==> [4/5] Syncing Terraform scaffolding..."
  cp "${INFRA_DCP_DIR}/main.tf" "$WORKSPACE_DIR/main.tf"
  cp "${INFRA_DCP_DIR}/variables.tf" "$WORKSPACE_DIR/variables.tf"
  cp "${INFRA_DCP_DIR}/outputs.tf" "$WORKSPACE_DIR/outputs.tf"
  ln -sfn "${INFRA_DCP_DIR}/modules" "$WORKSPACE_DIR/modules"

  (
    cd "$WORKSPACE_DIR"
    echo "    Running terraform init..."
    terraform init
  )

  # Check & configure service account impersonation for CLI commands
  echo "==> [5/5] Checking Service Account impersonation permissions..."
  CURRENT_USER=$(gcloud config get-value account 2>/dev/null || true)
  WORKFLOW_SA=$(cd "$WORKSPACE_DIR" && terraform output -raw ingestion_workflow_service_account_email 2>/dev/null || true)

  if [[ -n "$CURRENT_USER" && -n "$WORKFLOW_SA" ]]; then
    echo "    Authenticated user: ${CURRENT_USER}"
    echo "    Workflow Service Account: ${WORKFLOW_SA}"
    
    # Check if user already has TokenCreator role
    HAS_ROLE=$(gcloud iam service-accounts get-iam-policy "$WORKFLOW_SA" --project="$PROJECT" --format="json" 2>/dev/null | grep -i "${CURRENT_USER}" || true)

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
  echo " Ready to deploy:"
  echo "   1. Edit terraform.tfvars (uncomment custom images or version overrides)"
  echo "   2. Run 'terraform apply' to deploy"
  echo "   3. Run '$0 push-config --instance ${INSTANCE}' when done"
  echo "================================================================================"
  echo ""

  # Automatically navigate into the workspace directory
  if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    # Sourced mode (source ./connect.sh): changes directory in parent shell
    cd "$WORKSPACE_DIR"
  elif [[ -t 0 ]]; then
    # Interactive execution (./connect.sh): launches shell inside workspace
    echo "==> Entered workspace: ${WORKSPACE_DIR}"
    echo ""
    cd "$WORKSPACE_DIR"
    exec "${SHELL:-bash}"
  else
    cd "$WORKSPACE_DIR"
  fi

# ==============================================================================
# ACTION: PUSH-CONFIG
# ==============================================================================
elif [[ "$ACTION" == "push-config" ]]; then
  TFVARS_FILE="$WORKSPACE_DIR/terraform.tfvars"
  if [[ ! -f "$TFVARS_FILE" ]]; then
    echo "Error: Local configuration '$TFVARS_FILE' not found."
    echo "Have you run '$0 connect --instance $INSTANCE' first?"
    exit 1
  fi

  echo "==> Pushing local terraform.tfvars to Secret Manager ($SECRET_NAME)..."
  if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" &>/dev/null; then
    gcloud secrets versions add "$SECRET_NAME" \
      --data-file="$TFVARS_FILE" \
      --project="$PROJECT"
  else
    gcloud secrets create "$SECRET_NAME" \
      --data-file="$TFVARS_FILE" \
      --project="$PROJECT" \
      --replication-policy="automatic"
  fi
  echo "==> Secret successfully updated in GCP Secret Manager!"

else
  echo "Error: Unknown command '$ACTION'"
  echo ""
  print_usage
fi
