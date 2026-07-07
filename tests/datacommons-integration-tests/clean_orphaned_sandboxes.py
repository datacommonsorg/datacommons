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

"""Helper script to list and clean up leaked integration test GCP sandboxes.

It reconstructs local Terraform scaffolding to connect to GCS remote state
and execute 'terraform destroy' for orphaned namespaces.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print(f"Running command: {' '.join(args)} (cwd: {cwd or Path.cwd()})", flush=True)
    try:
        return subprocess.run(args, cwd=cwd, check=check, text=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"--- COMMAND FAILED: {' '.join(args)} ---", file=sys.stderr)
        if e.stdout:
            print(f"STDOUT:\n{e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"STDERR:\n{e.stderr}", file=sys.stderr)
        print("---------------------------------------", file=sys.stderr)
        raise e


def get_active_namespaces(tf_state_bucket: str) -> list[str]:
    """Lists all prefixes (namespaces) in GCS tf-state-bucket."""
    print(f"Listing active states in gs://{tf_state_bucket}/terraform/state/...")
    try:
        proc = run_command([
            "gcloud", "storage", "ls", f"gs://{tf_state_bucket}/terraform/state/"
        ])
        namespaces = []
        # Expected format: gs://bucket-name/terraform/state/itest-XXXX/
        pattern = rf"gs://{re.escape(tf_state_bucket)}/terraform/state/([^/]+)/"
        for line in proc.stdout.splitlines():
            match = re.match(pattern, line.strip())
            if match:
                namespaces.append(match.group(1))
        return sorted(list(set(namespaces)))
    except Exception as e:
        print(f"Error listing state directories: {e}", file=sys.stderr)
        return []


def destroy_sandbox(project_id: str, tf_state_bucket: str, namespace: str, workspace_root: Path) -> bool:
    """Reconstructs local state and executes terraform destroy."""
    print(f"\n=====================================================================")
    print(f" DESTROYING SANDBOX: namespace={namespace} in project={project_id}")
    print(f"=====================================================================")
    
    workspace_dir = Path(f"/tmp/workspace-purge-{namespace}")
    sandbox_dir = workspace_dir / namespace
    
    try:
        # Create directories
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)
        sandbox_dir.mkdir(parents=True)
        
        # Copy local infra modules & configs
        local_infra_dir = workspace_root / "infra" / "dcp"
        shutil.copy(local_infra_dir / "variables.tf", sandbox_dir / "variables.tf")
        shutil.copy(local_infra_dir / "outputs.tf", sandbox_dir / "outputs.tf")
        shutil.copy(local_infra_dir / "main.tf", sandbox_dir / "main.tf")
        shutil.copytree(local_infra_dir / "modules", sandbox_dir / "modules")
        
        # Construct backend.tf
        backend_content = f"""terraform {{
  backend "gcs" {{
    bucket = "{tf_state_bucket}"
    prefix = "terraform/state/{namespace}"
  }}
}}
"""
        (sandbox_dir / "backend.tf").write_text(backend_content, encoding="utf-8")
        
        # Construct terraform.tfvars
        tfvars_content = f"""project_id = "{project_id}"
namespace = "{namespace}"
spanner_create_instance = false
spanner_instance_id = "dcp-integration-test-shared-instance"
spanner_create_database = true
spanner_create_bigquery_reservation = false
datacommons_services_min_instances = 1
datacommons_services_max_instances = 1
"""
        (sandbox_dir / "terraform.tfvars").write_text(tfvars_content, encoding="utf-8")
        
        # Init & Destroy
        run_command(["terraform", "init"], cwd=sandbox_dir)
        run_command(["terraform", "destroy", "-auto-approve"], cwd=sandbox_dir)
        
        # Delete state file in GCS
        print(f"Removing GCS state files for namespace {namespace}...")
        run_command([
            "gcloud", "storage", "rm", "--recursive", 
            f"gs://{tf_state_bucket}/terraform/state/{namespace}/"
        ])
        
        print(f"Successfully destroyed sandbox resources for namespace: {namespace}")
        return True
        
    except Exception as e:
        print(f"Failed to destroy sandbox {namespace}: {e}", file=sys.stderr)
        return False
        
    finally:
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge orphaned GCP sandbox integration test resources.")
    parser.add_argument(
        "--project-id", default="datcom-ci", help="GCP project ID (default: datcom-ci)"
    )
    parser.add_argument(
        "--tf-state-bucket",
        default="tf-state-dcp-test-datcom-ci",
        help="GCS bucket for remote Terraform state (default: tf-state-dcp-test-datcom-ci)",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Specific namespace to destroy (e.g. itest-1234)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List active namespaces in the state bucket and exit",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Destroy all active namespaces found in the state bucket",
    )
    
    args = parser.parse_args()
    workspace_root = Path(__file__).resolve().parent.parent.parent
    
    # 1. Fetch active namespaces
    active_namespaces = get_active_namespaces(args.tf_state_bucket)
    if not active_namespaces:
        print("No active integration test state namespaces found in GCS.")
        return
        
    print(f"Active namespaces found ({len(active_namespaces)}):")
    for ns in active_namespaces:
        print(f"  - {ns}")
        
    if args.list:
        return
        
    # 2. Determine target namespaces
    targets = []
    if args.namespace:
        if args.namespace not in active_namespaces:
            print(f"Error: Namespace '{args.namespace}' was not found in GCS.", file=sys.stderr)
            sys.exit(1)
        targets = [args.namespace]
    elif args.all:
        targets = active_namespaces
    else:
        print("\nSpecify either --namespace <name>, --all, or --list. See --help for details.")
        sys.exit(1)
        
    # 3. Confirm destroy
    print(f"\nWARNING: This will permanently destroy all resources associated with the following namespaces: {', '.join(targets)}")
    confirm = input("Are you sure you want to proceed? [y/N]: ").strip().lower()
    if confirm not in ["y", "yes"]:
        print("Aborted.")
        sys.exit(0)
        
    # 4. Run destroys
    successes = 0
    failures = 0
    for ns in targets:
        if destroy_sandbox(args.project_id, args.tf_state_bucket, ns, workspace_root):
            successes += 1
        else:
            failures += 1
            
    print(f"\n=====================================================================")
    print(f" PURGE SUMMARY")
    print(f"=====================================================================")
    print(f"  Successes: {successes}")
    print(f"  Failures:  {failures}")
    if failures > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
