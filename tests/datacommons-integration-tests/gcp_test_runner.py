#!/usr/bin/env python3
# ruff: noqa: ANN401, ARG001, PTH101, PTH123, FBT001, FBT002, S603, S607, S310, S311, S108, BLE001, LOG015, G004
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

"""Automated system integration test script for Data Commons Platform sandboxes.

This script provisions a GCP sandbox, seeds custom MCF schema and CSV datasets,
triggers the ingestion workflow, and verifies Mixer/Website APIs.
"""

import argparse
import json
import logging
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

# Configure standard console logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def log_step(msg: str) -> None:
    logging.info(f">>> [STEP] {msg}")


def log_success(msg: str) -> None:
    logging.info(f"[SUCCESS] {msg}")


def log_error(msg: str) -> None:
    logging.error(f"[ERROR] {msg}")


def remove_readonly(func: Any, path: str, excinfo: Any) -> None:
    import stat

    os.chmod(path, stat.S_IWRITE)
    func(path)


def run_command(
    args: list[str],
    cwd: Path | None = None,
    check: bool = True,
    retries: int = 1,
    retry_delay: float = 2.0,
) -> subprocess.CompletedProcess:
    logging.info(f"Running command: {' '.join(args)} (cwd: {cwd or Path.cwd()})")
    for attempt in range(retries):
        try:
            return subprocess.run(
                args, cwd=cwd, check=check, text=True, capture_output=True
            )
        except subprocess.CalledProcessError as e:
            if attempt < retries - 1:
                logging.warning(
                    f"Command failed (attempt {attempt + 1}/{retries}). Retrying in {retry_delay}s... Error: {e}"
                )
                time.sleep(retry_delay)
                continue
            logging.error(f"--- COMMAND FAILED: {' '.join(args)} ---")
            if e.stdout:
                logging.error(f"STDOUT:\n{e.stdout}")
            if e.stderr:
                logging.error(f"STDERR:\n{e.stderr}")
            logging.error("---------------------------------------")
            raise e

    raise RuntimeError(
        f"Command execution loop finished without executing subprocess.run (retries={retries})"
    )


# =============================================================================
# Lifecycle Stage Implementations
# =============================================================================


def validate_mcf_file(mcf_path: Path) -> None:
    """Validates the syntax of local MCF file using datacommons_schema parser."""
    log_step(f"Validating local MCF schema file: {mcf_path.name}")
    try:
        # Import dynamically since the package is inside workspace virtual environment
        from datacommons_schema.parsers.mcf_parser import parse_mcf

        with open(mcf_path, encoding="utf-8") as f:
            nodes = list(parse_mcf(f))
        if not nodes:
            raise RuntimeError(
                f"MCF file {mcf_path.name} was successfully parsed but returned 0 nodes."
            )
        log_success(f"MCF schema is syntactically valid (parsed {len(nodes)} nodes)")
    except Exception as e:
        raise RuntimeError(
            f"MCF syntax validation failed for {mcf_path.name}: {e}"
        ) from e


def setup_workspace(workspace_dir: Path, namespace: str) -> None:
    """Ensure clean scratch workspace directories exist.
    Tries to destroy resources first if tfstate is present to avoid leakage.
    """
    sandbox_dir = workspace_dir / namespace
    if sandbox_dir.exists() and (sandbox_dir / "terraform.tfstate").exists():
        has_resources = False
        try:
            with open(sandbox_dir / "terraform.tfstate", encoding="utf-8") as f:
                state_data = json.load(f)
                if state_data.get("resources"):
                    has_resources = True
        except Exception:
            # If we fail to parse, assume resources might exist to be safe
            has_resources = True

        if has_resources:
            logging.info(
                f">>> [STEP] Existing active sandbox '{namespace}' detected with provisioned resources."
            )
            logging.info(
                ">>> [STEP] Attempting to clean up existing GCP resources first..."
            )
            try:
                # We need to run terraform init and destroy
                run_command(["terraform", "init"], cwd=sandbox_dir)
                run_command(["terraform", "destroy", "-auto-approve"], cwd=sandbox_dir)
                logging.info("[SUCCESS] Existing resources cleaned up successfully.")
            except Exception as e:
                logging.error(f"[ERROR] Failed to destroy existing resources: {e}")
                is_ci = bool(
                    os.environ.get("CLOUDBUILD_BUILD_ID")
                    or os.environ.get("GITHUB_ACTIONS")
                )
                if is_ci:
                    raise RuntimeError(
                        f"Aborting to prevent resource leakage. Clean up resources for namespace '{namespace}' manually."
                    ) from e
                print(
                    "\n[!] WARNING: Deleting this directory will permanently orphan these resources in GCP.",
                    flush=True,
                )
                try:
                    resp = (
                        input(
                            "Do you want to force delete the local workspace and proceed? [y/N]: "
                        )
                        .strip()
                        .lower()
                    )
                    if resp not in ["y", "yes"]:
                        print("Aborted by user.", flush=True)
                        sys.exit(1)
                except (KeyboardInterrupt, EOFError):
                    print("\nAborted.", flush=True)
                    sys.exit(1)

    if workspace_dir.exists():
        shutil.rmtree(workspace_dir, onerror=remove_readonly)
    workspace_dir.mkdir(parents=True)


def initialize_sandbox_scaffolding(
    workspace_root: Path,
    workspace_dir: Path,
    project_id: str,
    namespace: str,
    dc_api_key: str,
    tf_git_ref: str,
    tf_state_bucket: str = "",
) -> Path:
    """Runs dcp admin CLI to initialize configuration, then overrides with local infra files."""
    log_step("Initializing test sandbox directory...")
    init_args = [
        "uv",
        "run",
        "--project",
        str(workspace_root),
        "datacommons",
        "admin",
        "init",
        "--project-id",
        project_id,
        "--namespace",
        namespace,
        "--dc-api-key",
        dc_api_key,
    ]
    if tf_state_bucket:
        init_args.extend(["--tf-remote-state", "--tf-state-bucket", tf_state_bucket])
    else:
        init_args.append("--no-tf-remote-state")

    if tf_git_ref:
        init_args.extend(["--tf-git-ref", tf_git_ref])

    run_command(init_args, cwd=workspace_dir)
    sandbox_dir = workspace_dir / namespace
    log_success(f"Sandbox created at {sandbox_dir}")

    # Overwrite remote github scaffolding with local workspace files to test local modifications offline
    local_infra_dir = workspace_root / "infra" / "dcp"
    log_step(
        f"Replacing remote scaffolding with local workspace templates from {local_infra_dir}..."
    )
    shutil.copy(local_infra_dir / "variables.tf", sandbox_dir / "variables.tf")
    shutil.copy(local_infra_dir / "outputs.tf", sandbox_dir / "outputs.tf")
    shutil.copy(local_infra_dir / "main.tf", sandbox_dir / "main.tf")

    local_modules_dir = local_infra_dir / "modules"
    sandbox_modules_dir = sandbox_dir / "modules"
    if sandbox_modules_dir.exists():
        shutil.rmtree(sandbox_modules_dir, onerror=remove_readonly)
    shutil.copytree(local_modules_dir, sandbox_modules_dir)
    log_success("Successfully configured local scaffolding override.")
    return sandbox_dir


def configure_tfvars(sandbox_dir: Path, overrides: dict[str, str | int | bool]) -> None:
    """Reads existing HCL tfvars file, strips overridden keys, and appends overrides."""
    log_step("Configuring terraform.tfvars overrides...")
    tfvars_path = sandbox_dir / "terraform.tfvars"

    # Read existing tfvars content
    lines = []
    if tfvars_path.exists():
        with open(tfvars_path, encoding="utf-8") as f:
            lines = f.readlines()

    # Parse and strip keys that we want to override
    new_lines = []
    override_keys = set(overrides.keys())
    for line in lines:
        stripped = line.strip()
        # Skip commented lines or empty lines
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        # Split on '=' to find the key name
        if "=" in stripped:
            key = stripped.split("=")[0].strip()
            if key in override_keys:
                # Skip this line; it will be appended below with the override value
                continue
        new_lines.append(line)

    new_lines.append("\n# Integration Test Resource Allocations\n")
    for key, val in overrides.items():
        if isinstance(val, bool):
            formatted_val = str(val).lower()
        elif isinstance(val, int):
            formatted_val = str(val)
        else:
            formatted_val = f'"{val}"'
        new_lines.append(f"{key} = {formatted_val}\n")

    with open(tfvars_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    log_success("Added tfvars overrides")


def get_terraform_outputs(sandbox_dir: Path) -> dict[str, str]:
    """Retrieves and parses current Terraform outputs."""
    log_step("Retrieving Terraform outputs...")
    tf_out_proc = run_command(["terraform", "output", "-json"], cwd=sandbox_dir)
    tf_outputs = json.loads(tf_out_proc.stdout)

    outputs = {
        "bucket_name": tf_outputs["storage_artifacts_bucket_name"]["value"],
        "spanner_instance": tf_outputs["spanner_instance_id"]["value"],
        "spanner_database": tf_outputs["spanner_database_id"]["value"],
        "workflow_name": tf_outputs["ingestion_workflow_name"]["value"],
        "service_name": tf_outputs["datacommons_service_name"]["value"],
    }
    for key, val in outputs.items():
        log_success(f"{key.replace('_', ' ').title()}: {val}")
    return outputs


def run_terraform_apply(sandbox_dir: Path) -> dict[str, str]:
    """Runs terraform init, apply, and extracts parsed outputs."""
    log_step("Provisioning infrastructure via Terraform (this can take 5-7 minutes)...")
    run_command(["terraform", "init"], cwd=sandbox_dir, retries=3)
    run_command(["terraform", "apply", "-auto-approve"], cwd=sandbox_dir, retries=3)
    log_success("Terraform provisioning completed successfully")
    return get_terraform_outputs(sandbox_dir)


def upload_dataset_to_gcs(bucket_name: str, wages_data_dir: Path) -> None:
    """Verifies test files and uploads observations, schema, and configs to GCS."""
    log_step(f"Uploading files to GCS bucket: gs://{bucket_name}/ingestion/input/...")

    files_to_upload = [
        "average_annual_wage.csv",
        "average_annual_wage.mcf",
        "gender_wage_gap.csv",
        "gender_wage_gap.mcf",
        "config.json",
    ]

    for filename in files_to_upload:
        local_path = wages_data_dir / filename
        if not local_path.exists():
            raise FileNotFoundError(f"Required dataset file not found: {local_path}")

    log_success("Located OECD Wages Dataset files locally")

    for filename in files_to_upload:
        local_path = wages_data_dir / filename
        run_command(
            [
                "gcloud",
                "storage",
                "cp",
                str(local_path),
                f"gs://{bucket_name}/ingestion/input/{filename}",
            ],
            retries=3,
        )
    log_success("Uploaded dataset to GCS")


def run_database_schema_setup(workspace_root: Path, sandbox_dir: Path) -> None:
    """Initializes and seeds the Spanner database using the dcp admin CLI."""
    log_step("Initializing and seeding Spanner database...")
    run_command(
        [
            "uv",
            "run",
            "--project",
            str(workspace_root),
            "datacommons",
            "admin",
            "init-db",
        ],
        cwd=sandbox_dir,
    )
    log_success("Spanner database initialized and seeded successfully")


def trigger_and_poll_workflow(
    workspace_root: Path,
    sandbox_dir: Path,
    project_id: str,
    region: str,
    workflow_name: str,
) -> None:
    """Triggers workflows using dcp admin and polls executions until SUCCEEDED."""
    log_step("Starting ingestion workflow...")
    run_command(
        [
            "uv",
            "run",
            "--project",
            str(workspace_root),
            "datacommons",
            "admin",
            "ingest",
            "start",
        ],
        cwd=sandbox_dir,
    )
    log_success("Workflow ingestion run triggered")

    log_step("Polling workflow execution status...")
    workflow_state = "ACTIVE"
    workflow_execution_name = None
    timeout_seconds = 900  # 15 minutes max
    poll_interval = 20
    elapsed = 0

    while (
        workflow_state in ["ACTIVE", "RUNNING", "PENDING"] and elapsed < timeout_seconds
    ):
        time.sleep(poll_interval)
        elapsed += poll_interval

        # Fetch latest workflow execution status
        wf_args = [
            "gcloud",
            "workflows",
            "executions",
            "list",
            workflow_name,
            "--project",
            project_id,
            "--location",
            region,
            "--limit",
            "1",
            "--format",
            "json",
        ]
        wf_proc = run_command(wf_args, check=False)

        try:
            executions = json.loads(wf_proc.stdout)
            if executions:
                workflow_state = executions[0].get("state")
                workflow_execution_name = executions[0].get("name")
                logging.info(f"  [Poll {elapsed}s] Workflow status: {workflow_state}")
            else:
                logging.info(
                    f"  [Poll {elapsed}s] No active workflow executions found yet."
                )
        except Exception as e:
            logging.error(f"  [Poll {elapsed}s] Error parsing workflow status: {e}")

    if workflow_state != "SUCCEEDED":
        if workflow_execution_name:
            log_workflow_failure_details(workflow_execution_name)
        raise RuntimeError(
            f"Workflow failed to complete successfully. Final state: {workflow_state}"
        )

    log_success("Workflow finished successfully!")


def log_workflow_failure_details(workflow_execution_name: str) -> None:
    """Helper to fetch and print details on workflow errors."""
    parts = workflow_execution_name.split("/")
    if len(parts) >= 8:
        project_id = parts[1]
        region = parts[3]
        workflow_name = parts[5]
        execution_id = parts[7]
        console_url = f"https://console.cloud.google.com/workflows/workflow/{region}/{workflow_name}/execution/{execution_id}?project={project_id}"
        logging.error(f"GCP Console Workflow Execution Link:\n  {console_url}\n")

    log_step(
        f"Workflow execution failed. Retrieving execution logs from GCP: {workflow_execution_name}..."
    )
    desc_args = [
        "gcloud",
        "workflows",
        "executions",
        "describe",
        workflow_execution_name,
        "--format",
        "json",
    ]
    desc_proc = run_command(desc_args, check=False)
    if desc_proc.stdout:
        try:
            desc_json = json.loads(desc_proc.stdout)
            error_details = desc_json.get("error")
            if error_details:
                logging.error(
                    "=================== GCP WORKFLOW ERROR DETAILS ==================="
                )
                logging.error(json.dumps(error_details, indent=2))
                logging.error(
                    "=================================================================="
                )
            else:
                logging.error(
                    f"No error details found in execution output. Full describe output:\n{desc_proc.stdout}"
                )
        except Exception as parse_err:
            logging.error(
                f"Failed to parse workflow description response: {parse_err}\nRaw output:\n{desc_proc.stdout}"
            )


def verify_spanner_records(
    project_id: str,
    spanner_database: str,
    spanner_instance: str,
    min_expected_rows: int = 8,
) -> None:
    """Verifies that the database contains at least min_expected_rows observations."""
    log_step("Verifying Spanner data insertion...")
    span_args = [
        "gcloud",
        "spanner",
        "databases",
        "execute-sql",
        spanner_database,
        "--instance",
        spanner_instance,
        "--project",
        project_id,
        "--sql",
        "SELECT COUNT(*) FROM Observation",
        "--format",
        "json",
    ]
    span_proc = run_command(span_args)

    db_results = json.loads(span_proc.stdout)
    rows_count = int(db_results.get("rows", [["0"]])[0][0])
    log_success(f"Query returned {rows_count} observations in Spanner database")

    if rows_count < min_expected_rows:
        raise RuntimeError(
            f"Expected at least {min_expected_rows} observations, but found {rows_count} in Spanner."
        )


# Note: API verifications and assertions have been moved to pytest suites in tests/datacommons-integration-tests/suites/


def run_serving_proxy_tests(service_name: str, region: str, project_id: str) -> None:
    """Binds local port proxy to the Cloud Run service and runs HTTP API curls."""
    log_step("Testing Cloud Run serving endpoint via local proxy...")
    test_port = 18080
    proxy_proc = subprocess.Popen(
        [
            "gcloud",
            "run",
            "services",
            "proxy",
            service_name,
            "--region",
            region,
            "--project",
            project_id,
            "--port",
            str(test_port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Give proxy process 5 seconds to bind to port
    time.sleep(5)

    try:
        # Fetch direct V2 Node endpoint with retry loop to allow cold-start, warmup, and container rollover
        api_url = f"http://127.0.0.1:{test_port}/core/api/v2/node?nodes=average_annual_wage&property=-%3E*"
        max_retries = 18  # Allow up to 3 minutes for rolling update replication
        retry_interval = 10
        connected = False

        for i in range(max_retries):
            logging.info(
                f"Checking proxy V2 API for typeOf StatisticalVariable (attempt {i + 1}/{max_retries}): {api_url}"
            )
            try:
                with urllib.request.urlopen(api_url, timeout=10) as response:
                    status_code = response.getcode()
                    if status_code == 200:
                        resp_data = json.loads(response.read().decode("utf-8"))
                        data = resp_data.get("data", {}).get("average_annual_wage", {})
                        arcs = data.get("arcs", {})
                        types = arcs.get("typeOf", {}).get("nodes", [])
                        has_sv = any(
                            t.get("dcid") == "StatisticalVariable" for t in types
                        )
                        if has_sv:
                            log_success(
                                f"Proxy V2 API successfully returned typeOf StatisticalVariable on attempt {i + 1}!"
                            )
                            connected = True
                            break
                        logging.warning(
                            f"Proxy V2 API returned 200, but typeOf is missing (mismatch/warmup). Response: {resp_data}. Retrying in {retry_interval}s..."
                        )
                    else:
                        logging.warning(
                            f"Proxy V2 API returned unexpected status code: {status_code}. Retrying in {retry_interval}s..."
                        )
            except Exception as e:
                logging.warning(
                    f"Connection attempt failed: {e}. Retrying in {retry_interval}s..."
                )
            time.sleep(retry_interval)

        if not connected:
            raise RuntimeError(
                f"Failed to fetch a warm container instance containing the typeOf StatisticalVariable mapping after {max_retries * retry_interval}s."
            )

        # Run pytest E2E suites against the proxy port
        pytest_cmd = [
            "uv",
            "run",
            "pytest",
            "tests/datacommons-integration-tests/suites/",
            "--target-url",
            f"http://127.0.0.1:{test_port}",
        ]
        log_step(f"Running pytest suites: {' '.join(pytest_cmd)}")
        run_command(pytest_cmd, check=True)
        log_success("All pytest verification suites passed successfully!")

    except Exception as e:
        console_url = f"https://console.cloud.google.com/run/detail/{region}/{service_name}/logs?project={project_id}"
        logging.error(
            f"\n--- SERVING TEST FAILURE DIAGNOSTICS ---\n"
            f"GCP Cloud Run Service Console Link:\n"
            f"  {console_url}\n"
            f"-----------------------------------------\n"
        )
        raise e
    finally:
        logging.info("Terminating proxy subprocess...")
        proxy_proc.terminate()
        proxy_proc.wait()


def run_terraform_destroy(sandbox_dir: Path, workspace_dir: Path) -> None:
    """Destroys Terraform GCP sandbox resources and removes scratch workspace folders."""
    log_step("Cleaning up GCP sandbox resources (Terraform Destroy)...")
    try:
        run_command(
            ["terraform", "destroy", "-auto-approve"],
            cwd=sandbox_dir,
            check=False,
            retries=3,
        )
        log_success("GCP resources destroyed")

        # Delete local directories
        shutil.rmtree(workspace_dir, onerror=remove_readonly)
        log_success("Temporary local workspaces deleted")
    except Exception as cleanup_err:
        log_error(f"Failed to clean up resources cleanly: {cleanup_err}")


# =============================================================================
# API Key Resolver
# =============================================================================


def resolve_api_key(project_id: str, cli_key: str) -> str:
    """Resolves the Data Commons API key.

    1. Returns cli_key if provided.
    2. Returns env variable DC_API_KEY if set.
    3. Programmatically reads the latest version of the global secret 'dc-api-key'
       from GCP Secret Manager for the given project_id.
    """
    if cli_key:
        return cli_key

    env_key = os.environ.get("DC_API_KEY")
    if env_key:
        log_success(
            "Successfully resolved active API key from environment variable (DC_API_KEY)"
        )
        return env_key

    logging.info("API Key not provided. Resolving 'dc-api-key' from Secret Manager...")
    try:
        proc = subprocess.run(
            [
                "gcloud",
                "secrets",
                "versions",
                "access",
                "latest",
                "--secret",
                "dc-api-key",
                "--project",
                project_id,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        resolved_key = proc.stdout.strip()
        log_success("Successfully resolved active API key from Secret Manager")
        return resolved_key
    except Exception as err:
        logging.warning(
            f"Failed to read 'dc-api-key' secret from Secret Manager: {err}"
        )

    return ""


# =============================================================================
# Main Orchestrator
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Run end-to-end DCP integration test.")
    parser.add_argument(
        "--project-id", default="datcom-ci", help="GCP project ID to test in"
    )
    parser.add_argument(
        "--region", default="us-central1", help="GCP region to deploy in"
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Custom namespace (defaults to itest-XXXX)",
    )
    parser.add_argument(
        "--dcp-version",
        default="latest",
        help="Override default DCP version (controls all images and templates)",
    )

    parser.add_argument(
        "--keep-sandbox",
        action="store_true",
        help="Do not destroy sandbox on completion/failure",
    )
    parser.add_argument(
        "--reuse-sandbox",
        action="store_true",
        help="Skip terraform provision/destroy steps and reuse existing sandbox workspace",
    )
    parser.add_argument(
        "--dc-api-key",
        default=os.environ.get("DC_API_KEY", ""),
        help="Optional Google Data Commons API Key",
    )
    parser.add_argument(
        "--tf-git-ref",
        default="main",
        help="GCP Terraform templates git ref (e.g. branch, commit, tag)",
    )
    parser.add_argument(
        "--tf-state-bucket",
        default="tf-state-dcp-test-datcom-ci",
        help="GCS bucket for remote Terraform state (pass empty string to keep state local)",
    )

    args = parser.parse_args()

    # Generate random namespace if not provided
    namespace = args.namespace
    if not namespace:
        rand_suffix = f"{random.randint(1000, 9999)}"
        namespace = f"itest-{rand_suffix}"

    log_step(f"Starting Integration Test with namespace: {namespace}")

    workspace_dir = Path(f"/tmp/workspace-{namespace}")
    workspace_root = Path(__file__).resolve().parent.parent.parent

    # Track lifecycle state for cleanups
    terraform_provisioned = False
    sandbox_dir = None

    try:
        if args.reuse_sandbox:
            if not args.namespace:
                raise RuntimeError(
                    "Namespace must be specified when using --reuse-sandbox (e.g. --namespace itest-XXXX)"
                )
            sandbox_dir = workspace_dir / namespace
            if not sandbox_dir.exists():
                raise RuntimeError(f"Sandbox directory does not exist: {sandbox_dir}")
            log_step(f"Reusing existing sandbox namespace: {namespace}")
            outputs = get_terraform_outputs(sandbox_dir)
        else:
            # 1. Setup workspace
            setup_workspace(workspace_dir, namespace)

            # 1b. Validate local MCF schema syntax before deploying expensive cloud resources
            root_dir = Path(__file__).resolve().parent.parent.parent
            wages_data_dir = root_dir / "samples" / "OECD_wage_data"
            validate_mcf_file(wages_data_dir / "average_annual_wage.mcf")
            validate_mcf_file(wages_data_dir / "gender_wage_gap.mcf")

            # 2. Initialize configuration via CLI and setup overrides
            dc_key = resolve_api_key(args.project_id, args.dc_api_key)
            if not dc_key:
                raise RuntimeError(
                    "Data Commons API Key must be provided (either via --dc-api-key flag, "
                    "DC_API_KEY environment variable, or 'dc-api-key' Secret in GCP Secret Manager)."
                )

            sandbox_dir = initialize_sandbox_scaffolding(
                workspace_root=workspace_root,
                workspace_dir=workspace_dir,
                project_id=args.project_id,
                namespace=namespace,
                dc_api_key=dc_key,
                tf_git_ref=args.tf_git_ref,
                tf_state_bucket=args.tf_state_bucket,
            )

            # 3. Configure tfvars overrides
            tfvars_overrides: dict[str, str | int | bool] = {
                "spanner_create_instance": False,
                "spanner_instance_id": "dcp-integration-test-shared-instance",
                "spanner_create_database": True,
                "spanner_create_bigquery_reservation": False,
                "datacommons_services_min_instances": 1,
                "datacommons_services_max_instances": 1,
            }
            if args.dcp_version:
                tfvars_overrides["dcp_version"] = args.dcp_version

            configure_tfvars(sandbox_dir, tfvars_overrides)

            # 4. Provision Infrastructure (Terraform Apply)
            terraform_provisioned = True
            outputs = run_terraform_apply(sandbox_dir)

        # 5. Locate and upload OECD Wages Dataset files to GCS
        root_dir = Path(__file__).resolve().parent.parent.parent
        wages_data_dir = root_dir / "samples" / "OECD_wage_data"
        upload_dataset_to_gcs(outputs["bucket_name"], wages_data_dir)

        # 6. Initialize Spanner DB Schemas
        run_database_schema_setup(workspace_root, sandbox_dir)

        # 7. Start Ingestion Job & Poll execution state
        trigger_and_poll_workflow(
            workspace_root=workspace_root,
            sandbox_dir=sandbox_dir,
            project_id=args.project_id,
            region=args.region,
            workflow_name=outputs["workflow_name"],
        )

        # 8. Query Spanner to verify data was loaded (Mock datasets add 65 rows)
        verify_spanner_records(
            project_id=args.project_id,
            spanner_database=outputs["spanner_database"],
            spanner_instance=outputs["spanner_instance"],
            min_expected_rows=60,
        )

        # 9. Run Proxy verification to test the serving layers
        run_serving_proxy_tests(
            service_name=outputs["service_name"],
            region=args.region,
            project_id=args.project_id,
        )

        log_success("=== GCP INTEGRATION TEST PASSED SUCCESSFULLY ===")

    except Exception as e:
        log_error(f"Integration Test failed: {e}")
        # Re-raise to trigger sys.exit(1)
        raise e

    finally:
        # 10. Cleanup provisioned GCP Sandbox
        if terraform_provisioned and sandbox_dir:
            if args.keep_sandbox:
                log_step(
                    f"Keeping GCP Sandbox intact for debugging: namespace={namespace}"
                )
            else:
                run_terraform_destroy(sandbox_dir, workspace_dir)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
