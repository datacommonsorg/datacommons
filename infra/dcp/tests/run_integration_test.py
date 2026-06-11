#!/usr/bin/env python3
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
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def log_step(msg: str) -> None:
    print(f"\n>>> [STEP] {msg}", flush=True)


def log_success(msg: str) -> None:
    print(f"✔ [SUCCESS] {msg}", flush=True)


def log_error(msg: str) -> None:
    print(f"✖ [ERROR] {msg}", flush=True)


def remove_readonly(func, path, excinfo) -> None:
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)


def run_command(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print(f"Running command: {' '.join(args)} (cwd: {cwd or Path.cwd()})", flush=True)
    try:
        return subprocess.run(args, cwd=cwd, check=check, text=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"\n--- COMMAND FAILED: {' '.join(args)} ---", flush=True)
        if e.stdout:
            print(f"STDOUT:\n{e.stdout}", flush=True)
        if e.stderr:
            print(f"STDERR:\n{e.stderr}", flush=True)
        print("---------------------------------------", flush=True)
        raise e


def main() -> None:
    parser = argparse.ArgumentParser(description="Run end-to-end DCP integration test.")
    parser.add_argument("--project-id", default="datcom-ci", help="GCP project ID to test in")
    parser.add_argument("--region", default="us-central1", help="GCP region to deploy in")
    parser.add_argument("--namespace", default=None, help="Custom namespace (defaults to itest-XXXX)")
    parser.add_argument("--services-image", default=None, help="Override default serving services container image")
    parser.add_argument("--preprocessing-image", default=None, help="Override default data preprocessing image")
    parser.add_argument("--helper-image", default=None, help="Override default helper service image")
    parser.add_argument("--keep-sandbox", action="store_true", help="Do not destroy sandbox on completion/failure")
    parser.add_argument("--dc-api-key", default="", help="Optional Google Data Commons API Key")
    parser.add_argument("--tf-git-ref", default=None, help="GCP Terraform templates git ref (e.g. branch, commit, tag)")

    args = parser.parse_args()

    # Generate random namespace if not provided
    namespace = args.namespace
    if not namespace:
        rand_suffix = f"{random.randint(1000, 9999)}"
        namespace = f"itest-{rand_suffix}"

    log_step(f"Starting Integration Test with namespace: {namespace}")

    root_dir = Path(__file__).resolve().parent
    workspace_dir = root_dir / f"workspace-{namespace}"

    # Ensure clean workspace start
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    workspace_dir.mkdir()

    # Variables we need to track for clean-up
    terraform_provisioned = False

    try:
        # 1. Initialize configuration via CLI
        log_step("Initializing test sandbox directory...")
        init_args = [
            "uv", "run", "datacommons", "admin", "init",
            "--project-id", args.project_id,
            "--namespace", namespace,
            "--no-tf-remote-state"
        ]
        # Always pass a dc-api-key to bypass interactive console prompts in automated runs
        dc_key = args.dc_api_key or "dummy-key-for-test"
        init_args.extend(["--dc-api-key", dc_key])

        if args.tf_git_ref:
            init_args.extend(["--tf-git-ref", args.tf_git_ref])

        run_command(init_args, cwd=workspace_dir)
        sandbox_dir = workspace_dir / namespace
        log_success(f"Sandbox created at {sandbox_dir}")

        # 2. Add tfvars overrides (e.g. downscale Spanner to save costs, inject image overrides)
        log_step("Configuring terraform.tfvars overrides...")
        tfvars_path = sandbox_dir / "terraform.tfvars"
        
        # Read existing tfvars content
        with open(tfvars_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            # Comment out the default scale settings if they exist to replace them
            if "spanner_processing_units" in line or "spanner_create_bigquery_reservation" in line:
                continue
            new_lines.append(line)

        # Append overrides
        new_lines.append("\n# Integration Test Resource Allocations\n")
        new_lines.append("spanner_processing_units = 100\n") # Minimal Spanner PU
        new_lines.append("spanner_create_bigquery_reservation = false\n") # Disable to prevent conflict in shared projects
        new_lines.append("datacommons_services_min_instances = 1\n")
        new_lines.append("datacommons_services_max_instances = 1\n")

        if args.services_image:
            new_lines.append(f'datacommons_services_image = "{args.services_image}"\n')
        if args.preprocessing_image:
            new_lines.append(f'ingestion_preprocessing_job_image = "{args.preprocessing_image}"\n')
        if args.helper_image:
            new_lines.append(f'ingestion_helper_service_image = "{args.helper_image}"\n')

        with open(tfvars_path, "w") as f:
            f.writelines(new_lines)
        log_success("Added tfvars overrides")

        # 3. Provision Infrastructure (Terraform Apply)
        log_step("Provisioning infrastructure via Terraform (this can take 5-7 minutes)...")
        terraform_provisioned = True
        run_command(["terraform", "init"], cwd=sandbox_dir)
        run_command(["terraform", "apply", "-auto-approve"], cwd=sandbox_dir)
        log_success("Terraform provisioning completed successfully")

        # 4. Fetch Terraform output values
        log_step("Retrieving Terraform outputs...")
        tf_out_proc = run_command(["terraform", "output", "-json"], cwd=sandbox_dir)
        tf_outputs = json.loads(tf_out_proc.stdout)

        bucket_name = tf_outputs["storage_artifacts_bucket_name"]["value"]
        spanner_instance = tf_outputs["spanner_instance_id"]["value"]
        spanner_database = tf_outputs["spanner_database_id"]["value"]
        workflow_name = tf_outputs["ingestion_workflow_name"]["value"]
        service_name = tf_outputs["datacommons_service_name"]["value"]

        log_success(f"Bucket: {bucket_name}")
        log_success(f"Spanner Instance: {spanner_instance}")
        log_success(f"Spanner DB: {spanner_database}")
        log_success(f"Workflow: {workflow_name}")
        log_success(f"Service: {service_name}")

        # 5. Locate checked-in Frog Dataset files
        log_step("Locating Frog Dataset files...")
        root_dir = Path(__file__).resolve().parent
        frog_data_dir = root_dir / "test_data" / "frog_data"

        csv_path = frog_data_dir / "observations.csv"
        mcf_path = frog_data_dir / "schema.mcf"
        config_path = frog_data_dir / "config.json"

        if not (csv_path.exists() and mcf_path.exists() and config_path.exists()):
            raise FileNotFoundError(f"Frog Dataset files not found under {frog_data_dir}")

        log_success("Located Frog Dataset files locally")

        # 6. Upload static files to GCS Input Bucket
        log_step(f"Uploading files to GCS bucket: gs://{bucket_name}/ingestion/input/...")
        run_command(["gcloud", "storage", "cp", str(csv_path), f"gs://{bucket_name}/ingestion/input/observations.csv"])
        run_command(["gcloud", "storage", "cp", str(mcf_path), f"gs://{bucket_name}/ingestion/input/schema.mcf"])
        run_command(["gcloud", "storage", "cp", str(config_path), f"gs://{bucket_name}/ingestion/input/config.json"])
        log_success("Uploaded dataset to GCS")

        # 7. Initialize Spanner DB Schemas
        log_step("Initializing Spanner schemas...")
        run_command(["uv", "run", "datacommons", "admin", "init-db", "--init-only"], cwd=sandbox_dir)
        log_success("Spanner schema initialized successfully")

        # 8. Start Ingestion Job
        log_step("Starting ingestion workflow...")
        run_command(["uv", "run", "datacommons", "admin", "ingest", "start"], cwd=sandbox_dir)
        log_success("Workflow ingestion run triggered")

        # 9. Poll Workflow Execution until finished
        log_step("Polling workflow execution status...")
        workflow_state = "ACTIVE"
        timeout_seconds = 600 # 10 minutes max
        poll_interval = 20
        elapsed = 0

        while workflow_state in ["ACTIVE", "RUNNING", "PENDING"] and elapsed < timeout_seconds:
            time.sleep(poll_interval)
            elapsed += poll_interval

            # Fetch latest workflow execution status
            wf_args = [
                "gcloud", "workflows", "executions", "list", workflow_name,
                "--project", args.project_id,
                "--location", args.region,
                "--limit", "1",
                "--format", "json"
            ]
            wf_proc = run_command(wf_args, check=False)
            
            try:
                executions = json.loads(wf_proc.stdout)
                if executions:
                    workflow_state = executions[0].get("state")
                    print(f"  [Poll {elapsed}s] Workflow status: {workflow_state}", flush=True)
                else:
                    print(f"  [Poll {elapsed}s] No active workflow executions found yet.", flush=True)
            except Exception as e:
                print(f"  [Poll {elapsed}s] Error parsing workflow status: {e}", flush=True)

        if workflow_state != "SUCCEEDED":
            raise RuntimeError(f"Workflow failed to complete successfully. Final state: {workflow_state}")

        log_success("Workflow finished successfully!")

        # 10. Query Spanner to verify data was loaded
        log_step("Verifying Spanner data insertion...")
        span_args = [
            "gcloud", "spanner", "databases", "execute-sql", spanner_database,
            "--instance", spanner_instance,
            "--project", args.project_id,
            "--sql", "SELECT COUNT(*) FROM Observation",
            "--format", "json"
        ]
        span_proc = run_command(span_args)
        
        db_results = json.loads(span_proc.stdout)
        rows_count = int(db_results.get("rows", [["0"]])[0][0])
        log_success(f"Query returned {rows_count} observations in Spanner database")
        
        if rows_count < 8:
            raise RuntimeError(f"Expected at least 8 observations, but found {rows_count} in Spanner.")

        # 11. Run Proxy verification to test the serving layers
        log_step("Testing Cloud Run serving endpoint via local proxy...")
        test_port = 18080
        proxy_proc = subprocess.Popen(
            [
                "gcloud", "run", "services", "proxy", service_name,
                "--region", args.region,
                "--project", args.project_id,
                "--port", str(test_port)
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Give proxy process 5 seconds to bind to port
        time.sleep(5)

        try:
            # Fetch default landing page
            url = f"http://127.0.0.1:{test_port}/"
            print(f"Curling proxy url: {url}", flush=True)
            
            with urllib.request.urlopen(url, timeout=10) as response:
                status_code = response.getcode()
                log_success(f"Proxy returned status code: {status_code}")
                if status_code not in [200, 301, 302]:
                    raise RuntimeError(f"Expected HTTP 200 or redirection, got {status_code}")
        finally:
            print("Terminating proxy subprocess...", flush=True)
            proxy_proc.terminate()
            proxy_proc.wait()

        log_success("=== INTEGRATION TEST PASSED SUCCESSFULLY ===")

    except Exception as e:
        log_error(f"Integration Test failed: {e}")
        # Re-raise to trigger sys.exit(1)
        raise e

    finally:
        # 12. Cleanup provisioned GCP Sandbox
        if terraform_provisioned:
            if args.keep_sandbox:
                log_step(f"Keeping GCP Sandbox intact for debugging: namespace={namespace}")
            else:
                log_step("Cleaning up GCP sandbox resources (Terraform Destroy)...")
                try:
                    run_command(["terraform", "destroy", "-auto-approve"], cwd=sandbox_dir, check=False)
                    log_success("GCP resources destroyed")
                    
                    # Delete local directories
                    shutil.rmtree(workspace_dir, onerror=remove_readonly)
                    log_success("Temporary local workspaces deleted")
                except Exception as cleanup_err:
                    log_error(f"Failed to clean up resources cleanly: {cleanup_err}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
