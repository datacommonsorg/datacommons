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

This script executes the steps in runbook.md end-to-end inside a temporary
sandboxed environment, validates data load, and verifies the web server.
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
    args: list[str], cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    logging.info(f"Running command: {' '.join(args)} (cwd: {cwd or Path.cwd()})")
    try:
        return subprocess.run(
            args, cwd=cwd, check=check, text=True, capture_output=True
        )
    except subprocess.CalledProcessError as e:
        logging.error(f"--- COMMAND FAILED: {' '.join(args)} ---")
        if e.stdout:
            logging.error(f"STDOUT:\n{e.stdout}")
        if e.stderr:
            logging.error(f"STDERR:\n{e.stderr}")
        logging.error("---------------------------------------")
        raise e


# =============================================================================
# Lifecycle Stage Implementations
# =============================================================================


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
                    )
                else:
                    print(
                        f"\n[!] WARNING: Deleting this directory will permanently orphan these resources in GCP.",
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
        "--no-tf-remote-state",
        "--dc-api-key",
        dc_api_key,
    ]
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


def run_terraform_apply(sandbox_dir: Path) -> dict[str, str]:
    """Runs terraform init, apply, and extracts parsed outputs."""
    log_step("Provisioning infrastructure via Terraform (this can take 5-7 minutes)...")
    run_command(["terraform", "init"], cwd=sandbox_dir)
    run_command(["terraform", "apply", "-auto-approve"], cwd=sandbox_dir)
    log_success("Terraform provisioning completed successfully")

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


def upload_dataset_to_gcs(bucket_name: str, frog_data_dir: Path) -> None:
    """Verifies test files and uploads observations, schema, and configs to GCS."""
    log_step(f"Uploading files to GCS bucket: gs://{bucket_name}/ingestion/input/...")

    csv_path = frog_data_dir / "observations.csv"
    mcf_path = frog_data_dir / "schema.mcf"
    config_path = frog_data_dir / "config.json"

    if not (csv_path.exists() and mcf_path.exists() and config_path.exists()):
        raise FileNotFoundError(f"Frog Dataset files not found under {frog_data_dir}")

    log_success("Located Frog Dataset files locally")

    for filename, remote_dest in [
        ("observations.csv", "observations.csv"),
        ("schema.mcf", "schema.mcf"),
        ("config.json", "config.json"),
    ]:
        local_path = frog_data_dir / filename
        run_command(
            [
                "gcloud",
                "storage",
                "cp",
                str(local_path),
                f"gs://{bucket_name}/ingestion/input/{remote_dest}",
            ]
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


def run_serving_proxy_tests(service_name: str, region: str, project_id: str) -> None:
    """Binds local port proxy to the Cloud Run service and runs HTTP landing page & API curls."""
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
        # Fetch default landing page with retry loop to allow cold-start / warmup
        url = f"http://127.0.0.1:{test_port}/"
        max_retries = 12
        retry_interval = 10
        connected = False

        for i in range(max_retries):
            logging.info(f"Curling proxy url (attempt {i+1}/{max_retries}): {url}")
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    status_code = response.getcode()
                    if status_code in [200, 301, 302]:
                        log_success(f"Proxy returned success status code: {status_code}")
                        connected = True
                        break
                    else:
                        logging.warning(
                            f"Proxy returned unexpected status code: {status_code}. Retrying in {retry_interval}s..."
                        )
            except Exception as e:
                logging.warning(
                    f"Connection attempt failed: {e}. Retrying in {retry_interval}s..."
                )
            time.sleep(retry_interval)

        if not connected:
            raise RuntimeError(
                f"Failed to connect to Cloud Run serving endpoint via local proxy after {max_retries * retry_interval}s."
            )

        # Query API to verify the ingested data is queryable (tests the latest snapshot behavior)
        api_url = f"http://127.0.0.1:{test_port}/api/node/triples/out/Count_Frog_Green"
        logging.info(f"Curling proxy API url: {api_url}")
        with urllib.request.urlopen(api_url, timeout=10) as response:
            status_code = response.getcode()
            log_success(f"Proxy API returned status code: {status_code}")
            if status_code != 200:
                raise RuntimeError(f"Expected HTTP 200, got {status_code}")

            resp_data = json.loads(response.read().decode("utf-8"))
            if "typeOf" not in resp_data:
                raise RuntimeError(
                    f"Expected 'typeOf' in API response, but got: {resp_data}"
                )

            types = resp_data["typeOf"]
            has_sv = any(t.get("dcid") == "StatisticalVariable" for t in types)
            if not has_sv:
                raise RuntimeError(
                    f"Expected 'StatisticalVariable' type in API response, but got: {resp_data}"
                )

            log_success(
                "Verified ingested node 'Count_Frog_Green' exists and has type 'StatisticalVariable'"
            )

        # Test semantic NL Query API (explore flow)
        nl_url = f"http://127.0.0.1:{test_port}/api/explore/detect-and-fulfill?q=Number+of+frogs+in+United+States+of+America"
        logging.info(f"Testing NL query via proxy url: {nl_url}")
        req = urllib.request.Request(
            nl_url,
            data=json.dumps({"contextHistory": []}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = response.getcode()
            log_success(f"Proxy NL API returned status code: {status_code}")
            if status_code != 200:
                raise RuntimeError(f"Expected HTTP 200, got {status_code}")

            resp_data = json.loads(response.read().decode("utf-8"))
            config = resp_data.get("config")
            if not config:
                raise RuntimeError(
                    f"Expected 'config' in NL response, but got: {resp_data}"
                )

            metadata = config.get("metadata")
            if not metadata:
                raise RuntimeError(
                    f"Expected 'config.metadata' in NL response, but got: {resp_data}"
                )

            place_dcids = metadata.get("placeDcid")
            if not place_dcids or "country/USA" not in place_dcids:
                raise RuntimeError(
                    f"Expected 'placeDcid' list to contain 'country/USA', got '{place_dcids}'"
                )

            log_success(
                "Verified semantic NL query returns valid placeDcid 'country/USA'"
            )
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
        log_success("Successfully resolved active API key from environment variable (DC_API_KEY)")
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
        "--services-image",
        default="gcr.io/datcom-ci/datacommons-services:latest",
        help="Override default serving services container image",
    )
    parser.add_argument(
        "--preprocessing-image",
        default="gcr.io/datcom-ci/datacommons-data:latest",
        help="Override default data preprocessing image",
    )
    # Use stable helper tag by default until stable/local pushes are fixed for ingestion (aligning with the default in tests/datacommons-integration-tests/docker-compose.test.yml).
    parser.add_argument(
        "--helper-image",
        default="gcr.io/datcom-ci/datacommons-ingestion-helper:stable",
        help="Override default helper service image",
    )
    parser.add_argument(
        "--keep-sandbox",
        action="store_true",
        help="Do not destroy sandbox on completion/failure",
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
        # 1. Setup workspace
        setup_workspace(workspace_dir, namespace)

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
        )

        # 3. Configure tfvars overrides
        tfvars_overrides: dict[str, str | int | bool] = {
            "spanner_processing_units": 100,
            "spanner_create_bigquery_reservation": False,
            "datacommons_services_min_instances": 1,
            "datacommons_services_max_instances": 1,
        }
        if args.services_image:
            tfvars_overrides["datacommons_services_image"] = args.services_image
        if args.preprocessing_image:
            tfvars_overrides["ingestion_preprocessing_job_image"] = (
                args.preprocessing_image
            )
        if args.helper_image:
            tfvars_overrides["ingestion_helper_service_image"] = args.helper_image

        configure_tfvars(sandbox_dir, tfvars_overrides)

        # 4. Provision Infrastructure (Terraform Apply)
        terraform_provisioned = True
        outputs = run_terraform_apply(sandbox_dir)

        # 5. Locate and upload Frog Dataset files to GCS
        frog_data_dir = Path(__file__).resolve().parent / "test_data" / "frog_data"
        upload_dataset_to_gcs(outputs["bucket_name"], frog_data_dir)

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

        # 8. Query Spanner to verify data was loaded
        verify_spanner_records(
            project_id=args.project_id,
            spanner_database=outputs["spanner_database"],
            spanner_instance=outputs["spanner_instance"],
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
