#!/usr/bin/env bash
#
# Data Commons Platform (DCP) - Setup Pre-flight Validation Script
# Automates operating system detection, CLI dependency checks, auto-installers,
# authentication verification, and GCP API enablement.
#

set -euo pipefail

# Standard formatting variables
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0;0m' # No Color

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

# 1. OS Detection
OS_TYPE="$(uname -s)"
log_info "Detected operating system: ${OS_TYPE}"

if [[ "${OS_TYPE}" != "Darwin" && "${OS_TYPE}" != "Linux" ]]; then
    log_error "Unsupported operating system: ${OS_TYPE}. This setup requires macOS or Linux."
    exit 1
fi

# Ensure base commands exist
for cmd in curl unzip grep; do
    if ! command -v "$cmd" &> /dev/null; then
        log_error "Required system utility '$cmd' is missing. Please install it first."
        exit 1
    fi
done

# 2. Check & Install uv
if command -v uv &> /dev/null; then
    log_success "uv package manager is already installed: $(uv --version)"
else
    log_warning "uv is missing. Attempting standalone installation..."
    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        # Source the environment to update PATH immediately
        if [ -f "$HOME/.local/bin/env" ]; then
            source "$HOME/.local/bin/env"
        elif [ -f "$HOME/.cargo/env" ]; then
            source "$HOME/.cargo/env"
        fi
        export PATH="$HOME/.local/bin:$PATH"
        if command -v uv &> /dev/null; then
            log_success "uv was successfully installed: $(uv --version)"
        else
            log_error "uv was installed but could not be found in PATH. Please restart your terminal and re-run."
            exit 1
        fi
    else
        log_error "Failed to install uv. Please install it manually from https://astral.sh/uv"
        exit 1
    fi
fi

# 3. Check & Install Terraform
if command -v terraform &> /dev/null; then
    log_success "Terraform is already installed: $(terraform -version | head -n 1)"
else
    log_warning "Terraform is missing. Attempting installation..."
    if [[ "${OS_TYPE}" == "Darwin" ]]; then
        if command -v brew &> /dev/null; then
            log_info "Using Homebrew to install Terraform..."
            brew tap hashicorp/tap
            brew install hashicorp/tap/terraform
        else
            log_warning "Homebrew not found. Downloading standalone Terraform binary..."
            TF_URL="https://releases.hashicorp.com/terraform/1.8.0/terraform_1.8.0_darwin_amd64.zip"
            curl -Lo /tmp/terraform.zip "${TF_URL}"
            unzip -o /tmp/terraform.zip -d /usr/local/bin/ || unzip -o /tmp/terraform.zip -d "$HOME/.local/bin/"
            rm /tmp/terraform.zip
        fi
    elif [[ "${OS_TYPE}" == "Linux" ]]; then
        if command -v apt-get &> /dev/null; then
            log_info "Using APT to install Terraform..."
            sudo apt-get update && sudo apt-get install -y gnupg software-properties-common wget
            wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg > /dev/null
            echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
            sudo apt-get update && sudo apt-get install -y terraform
        else
            log_warning "APT package manager not found. Downloading standalone Terraform binary..."
            TF_URL="https://releases.hashicorp.com/terraform/1.8.0/terraform_1.8.0_linux_amd64.zip"
            curl -Lo /tmp/terraform.zip "${TF_URL}"
            mkdir -p "$HOME/.local/bin"
            unzip -o /tmp/terraform.zip -d "$HOME/.local/bin"
            export PATH="$HOME/.local/bin:$PATH"
            rm /tmp/terraform.zip
        fi
    fi

    # Verify install
    if command -v terraform &> /dev/null; then
        log_success "Terraform was successfully installed: $(terraform -version | head -n 1)"
    else
        log_error "Terraform installation failed. Please install it manually."
        exit 1
    fi
fi

# 4. Check & Guide gcloud SDK
if command -v gcloud &> /dev/null; then
    log_success "gcloud CLI is already installed: $(gcloud --version | head -n 1)"
else
    log_error "gcloud CLI is missing."
    log_info "To proceed, please download and install Google Cloud SDK by running the following commands or visiting: https://cloud.google.com/sdk/docs/install"
    if [[ "${OS_TYPE}" == "Darwin" ]]; then
        log_info "macOS command: brew install --cask google-cloud-sdk"
    elif [[ "${OS_TYPE}" == "Linux" ]]; then
        log_info "Linux quick-install: curl https://sdk.cloud.google.com | bash"
    fi
    exit 1
fi

# 5. Validate active GCP project setting
ACTIVE_PROJECT="$(gcloud config get-value project 2>/dev/null || echo "")"
if [[ -z "${ACTIVE_PROJECT}" || "${ACTIVE_PROJECT}" == "(unset)" ]]; then
    log_warning "No active GCP project is configured in gcloud."
    log_info "Please set your project context using: gcloud config set project [PROJECT_ID]"
else
    log_success "Active GCP project context verified: ${ACTIVE_PROJECT}"
fi

# 6. Verify Authentication State
log_info "Checking GCP authentication state..."
if gcloud auth application-default print-access-token &> /dev/null; then
    log_success "Active Application Default Credentials (ADC) verified."
else
    log_warning "No active Application Default Credentials (ADC) found."
    log_info "Please login by running: gcloud auth application-default login"
    log_info "Once authentication completes, re-run this pre-flight validation."
    exit 2
fi

log_success "DCP Setup Pre-flight checks completed successfully!"
