#!/usr/bin/env bash
#
# Data Commons Platform (DCP) - Agentic Assistant Installer
# Autonomously provisions a workspace with partner setup and operations skills,
# virtual environment, CLI, and triggers validation.
#

set -euo pipefail

# ==========================================
# Overridable Repository Settings (For dev branch & fork overrides)
# ==========================================
DCP_GIT_REPO="${DCP_GIT_REPO:-https://github.com/datacommonsorg/datacommons.git}"
DCP_GIT_BRANCH="${DCP_GIT_BRANCH:-main}"
DCP_GITHUB_RAW_BASE="${DCP_GITHUB_RAW_BASE:-https://raw.githubusercontent.com/datacommonsorg/datacommons}"

# ==========================================
# 1. Initialization & Logging Functions
# ==========================================

setup_colors() {
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0;0m' # No Color
}

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

# ==========================================
# 2. Target Directory Resolution
# ==========================================

resolve_target_dir() {
    local current_dir
    current_dir="$(pwd)"
    echo -e -n "${YELLOW}[INPUT]${NC} Where would you like to install the Data Commons agent? [Default: ${current_dir}]: "
    read -r user_input
    
    # Use current directory if input is empty
    local target_path="${user_input:-${current_dir}}"
    
    # Resolve absolute path
    mkdir -p "${target_path}"
    TARGET_DIR="$(cd "${target_path}" && pwd)"
    log_info "Target workspace resolved to: ${TARGET_DIR}"
}

# ==========================================
# 3. Environment & Mode Detection
# ==========================================

detect_mode() {
    log_info "Detecting running environment mode..."
    
    # Get current script path
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Check if we are running inside a local cloned dc-datacommons repository
    if [[ "${script_dir}" == *"packages/datacommons-cli/scripts"* ]]; then
        DEV_MODE=true
        # Root repo directory is 3 levels up from the script folder
        REPO_ROOT="$(cd "${script_dir}/../../.." && pwd)"
        log_success "Development Mode Detected! Local Repository Root: ${REPO_ROOT}"
    else
        DEV_MODE=false
        log_info "Production/Remote Mode Detected. Assets will be fetched from GitHub."
    fi
}

# ==========================================
# 4. Skill Deployment (Local vs. Remote)
# ==========================================

copy_local_skills() {
    log_info "Copying local skill assets in Development Mode..."
    
    local local_skills_source="${REPO_ROOT}/packages/datacommons-cli/datacommons_cli/skills"
    local target_skills_dest="${TARGET_DIR}/.agent/skills"
    
    if [[ ! -d "${local_skills_source}" ]]; then
        log_error "Source skills folder not found at: ${local_skills_source}"
        exit 1
    fi
    
    mkdir -p "${target_skills_dest}"
    cp -R "${local_skills_source}/dcp-setup" "${target_skills_dest}/"
    cp -R "${local_skills_source}/dcp-ops" "${target_skills_dest}/"
    
    # Ensure scripts are marked executable
    chmod +x "${target_skills_dest}/dcp-setup/scripts/"*.sh 2>/dev/null || true
    
    log_success "Skills successfully copied to: ${target_skills_dest}"
}

download_remote_skills() {
    log_info "Downloading remote skill assets from GitHub..."
    
    local github_raw_url="${DCP_GITHUB_RAW_BASE}/${DCP_GIT_BRANCH}/packages/datacommons-cli/datacommons_cli/skills"
    local target_skills_dest="${TARGET_DIR}/.agent/skills"
    
    local files_to_fetch=(
        "dcp-setup/SKILL.md"
        "dcp-setup/scripts/preflight_check.sh"
        "dcp-setup/scripts/poll_iam.sh"
        "dcp-ops/SKILL.md"
    )
    
    for file_path in "${files_to_fetch[@]}"; do
        local dest_file="${target_skills_dest}/${file_path}"
        local source_url="${github_raw_url}/${file_path}"
        
        # Create parent directory for the file
        mkdir -p "$(dirname "${dest_file}")"
        
        log_info "Fetching: ${file_path}..."
        if ! curl -sSfL "${source_url}" -o "${dest_file}"; then
            log_error "Failed to fetch file from: ${source_url}"
            exit 1
        fi
    done
    
    # Ensure scripts are marked executable
    chmod +x "${target_skills_dest}/dcp-setup/scripts/"*.sh 2>/dev/null || true
    
    log_success "Skills successfully downloaded to: ${target_skills_dest}"
}

deploy_skills() {
    if [ "${DEV_MODE}" = true ]; then
        copy_local_skills
    else
        download_remote_skills
    fi
}

# ==========================================
# 5. Python Virtual Env & Package Setup
# ==========================================

ensure_uv_installed() {
    if ! command -v uv &> /dev/null; then
        log_warning "uv package manager is missing. Attempting automatic installation..."
        if curl -LsSf https://astral.sh/uv/install.sh | sh; then
            export PATH="$HOME/.local/bin:$PATH"
        else
            log_error "Failed to install uv automatically. Please install it manually from https://astral.sh/uv"
            exit 1
        fi
    fi
}

initialize_python_env() {
    log_info "Provisioning Python virtual environment..."
    ensure_uv_installed
    
    cd "${TARGET_DIR}"
    uv venv
    
    # Install package in target virtual environment
    if [ "${DEV_MODE}" = true ]; then
        log_info "Installing local datacommons CLI package in editable mode..."
        # Resolve relative package paths from local repository root
        uv pip install -e "${REPO_ROOT}/packages/datacommons-cli" -e "${REPO_ROOT}/packages/datacommons-admin"
    else
        log_info "Installing datacommons CLI package from GitHub release..."
        uv pip install "git+${DCP_GIT_REPO}@${DCP_GIT_BRANCH}#subdirectory=packages/datacommons-cli"
    fi
    
    log_success "Python virtual environment and CLI package successfully configured!"
}

# ==========================================
# 6. Pre-flight Orchestration
# ==========================================

run_preflight_validation() {
    log_info "Triggering local pre-flight checks..."
    
    local preflight_script="${TARGET_DIR}/.agent/skills/dcp-setup/scripts/preflight_check.sh"
    
    if [[ -f "${preflight_script}" ]]; then
        bash "${preflight_script}"
    else
        log_warning "Pre-flight script not found at: ${preflight_script}. Skipping."
    fi
}

# ==========================================
# 7. Main Execution Sequence
# ==========================================

main() {
    setup_colors
    log_info "========================================="
    log_info "   Data Commons Platform Agent Installer "
    log_info "========================================="
    
    resolve_target_dir
    detect_mode
    deploy_skills
    initialize_python_env
    run_preflight_validation
    
    log_success "===================================================="
    log_success "   DCP Agent Installation Completed Successfully!  "
    log_success "===================================================="
    log_info "Your workspace at '${TARGET_DIR}' is fully configured."
    log_info "Please open your agentic assistant inside this workspace and ask:"
    log_info "\"Help me set up my Data Commons\""
    log_info "===================================================="
}

# Trigger Main
main
