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

"""Operational Janitor for Orphaned Ephemeral Prober Resources.

Role in Development Cycle:
--------------------------
This script is strictly a developer & operational cleanup utility. It is NOT
part of the automated prober execution pipeline.

Under standard automated execution:
`prober_runner.py` wraps the entire test lifecycle in `try...finally` blocks
and traps OS signals (SIGTERM/SIGINT) to automatically guarantee `terraform destroy`
executes immediately after tests finish.

When to use this janitor script:
1. Post-Debugging Cleanup: After running `prober_runner.py --skip-destroy` to
   inspect live Spanner databases, Cloud Workflows, or Cloud Run logs during a
   failure investigation.
2. Abrupt Crashes / Force Kills: When a local or manual run was abruptly
   interrupted (e.g., SIGKILL, terminal closed, network failure) before Terraform
   could execute its teardown step.

Safety Guarantees:
------------------
- Scans 13 GCP resource types for temporary resources prefixed with 'prober-[a-f0-9]{8}'.
- Explicitly excludes the permanent prober daemon infrastructure (e.g., 'dcp-prober-sa', 'dcp-prober-tfvars').
- Interactively prompts for confirmation ([y/N], defaulting to No) before deleting every single resource.
"""

import argparse
import json
import os
import re
import subprocess


def is_ephemeral_prober_resource(name: str) -> bool:
    """Matches only ephemeral prober instances (prober-<8-hex-chars>) to prevent accidental deletion of other resources."""
    return bool(re.match(r"^prober-[a-f0-9]{8}", name))


def run_gcloud(args: list[str], project: str) -> list[dict] | dict:
    """Executes a gcloud CLI command and parses the JSON response."""
    res = subprocess.run(
        ["gcloud"] + args + ["--project", project, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return []
    try:
        return json.loads(res.stdout) if res.stdout.strip() else []
    except json.JSONDecodeError:
        return []


def confirm_delete(resource_type: str, resource_id: str) -> bool:
    """Prompts the user explicitly before deleting any resource. Defaults to NO."""
    try:
        reply = (
            input(f"  ❓ Delete {resource_type} '{resource_id}'? [y/N]: ")
            .strip()
            .lower()
        )
        return reply in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled.")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Safe interactive cleanup of orphaned ephemeral prober resources."
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GCP_PROJECT", "datcom-dcp"),
        help="GCP Project ID to clean (default: datcom-dcp)",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("GCP_REGION", "us-central1"),
        help="GCP Region (default: us-central1)",
    )
    args = parser.parse_args()

    project = args.project
    region = args.region

    print("=" * 80)
    print(f"SAFE INTERACTIVE EPHEMERAL PROBER RESOURCE CLEANUP FOR PROJECT: {project}")
    print("=" * 80)

    # 1. Clean GCS Buckets
    print("\n==> 1. Checking GCS Buckets...")
    buckets = run_gcloud(["storage", "buckets", "list"], project)
    for b in buckets:
        name = b.get("name", "")
        if is_ephemeral_prober_resource(name):
            if confirm_delete("GCS Bucket", f"gs://{name}"):
                print(f"  Deleting bucket gs://{name}...")
                subprocess.run(
                    ["gcloud", "storage", "rm", "--recursive", f"gs://{name}"],
                    check=False,
                )
            else:
                print(f"  Skipped gs://{name}")

    # 2. Clean Secret Manager Secrets
    print("\n==> 2. Checking Secret Manager Secrets...")
    secrets = run_gcloud(["secrets", "list"], project)
    for s in secrets:
        name = s.get("name", "").split("/")[-1]
        if is_ephemeral_prober_resource(name):
            if confirm_delete("Secret", name):
                print(f"  Deleting secret {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "secrets",
                        "delete",
                        name,
                        f"--project={project}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 3. Clean Cloud Run Services
    print("\n==> 3. Checking Cloud Run Services...")
    services = run_gcloud(["run", "services", "list", f"--region={region}"], project)
    for svc in services:
        name = svc.get("metadata", {}).get("name", "")
        if is_ephemeral_prober_resource(name):
            if confirm_delete("Cloud Run Service", name):
                print(f"  Deleting Cloud Run service {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "run",
                        "services",
                        "delete",
                        name,
                        f"--project={project}",
                        f"--region={region}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 4. Clean Cloud Run Jobs
    print("\n==> 4. Checking Cloud Run Jobs...")
    jobs = run_gcloud(["run", "jobs", "list", f"--region={region}"], project)
    for job in jobs:
        name = job.get("metadata", {}).get("name", "")
        if is_ephemeral_prober_resource(name):
            if confirm_delete("Cloud Run Job", name):
                print(f"  Deleting Cloud Run Job {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "run",
                        "jobs",
                        "delete",
                        name,
                        f"--project={project}",
                        f"--region={region}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 5. Clean Cloud Workflows
    print("\n==> 5. Checking Cloud Workflows...")
    workflows = run_gcloud(["workflows", "list", f"--location={region}"], project)
    for wf in workflows:
        name = wf.get("name", "").split("/")[-1]
        if is_ephemeral_prober_resource(name):
            if confirm_delete("Cloud Workflow", name):
                print(f"  Deleting Cloud Workflow {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "workflows",
                        "delete",
                        name,
                        f"--project={project}",
                        f"--location={region}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 6. Clean Cloud Spanner Instances
    print("\n==> 6. Checking Cloud Spanner Instances...")
    spanner_instances = run_gcloud(["spanner", "instances", "list"], project)
    for inst in spanner_instances:
        name = inst.get("name", "").split("/")[-1]
        if is_ephemeral_prober_resource(name):
            if confirm_delete("Spanner Instance", name):
                print(f"  Deleting Spanner Instance {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "spanner",
                        "instances",
                        "delete",
                        name,
                        f"--project={project}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 7. Clean MemoryStore Redis Instances
    print("\n==> 7. Checking MemoryStore Redis Instances...")
    redis_instances = run_gcloud(
        ["redis", "instances", "list", f"--region={region}"], project
    )
    for inst in redis_instances:
        name = inst.get("name", "").split("/")[-1]
        if is_ephemeral_prober_resource(name):
            if confirm_delete("Redis Instance", name):
                print(f"  Deleting Redis Instance {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "redis",
                        "instances",
                        "delete",
                        name,
                        f"--region={region}",
                        f"--project={project}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 8. Clean Serverless VPC Access Connectors
    print("\n==> 8. Checking Serverless VPC Access Connectors...")
    connectors = run_gcloud(
        ["compute", "vpc-access", "connectors", "list", f"--region={region}"], project
    )
    for conn in connectors:
        name = conn.get("name", "").split("/")[-1]
        if is_ephemeral_prober_resource(name):
            if confirm_delete("VPC Connector", name):
                print(f"  Deleting VPC Connector {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "compute",
                        "vpc-access",
                        "connectors",
                        "delete",
                        name,
                        f"--region={region}",
                        f"--project={project}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 9. Clean Service Accounts
    print("\n==> 9. Checking Service Accounts...")
    sas = run_gcloud(["iam", "service-accounts", "list"], project)
    for sa in sas:
        email = sa.get("email", "")
        name = email.split("@")[0]
        if is_ephemeral_prober_resource(name):
            if confirm_delete("Service Account", email):
                print(f"  Deleting Service Account {email}...")
                subprocess.run(
                    [
                        "gcloud",
                        "iam",
                        "service-accounts",
                        "delete",
                        email,
                        f"--project={project}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {email}")

    # 10. Clean BigQuery Connections
    print("\n==> 10. Checking BigQuery Connections...")
    bq_conns = run_gcloud(
        ["bigquery", "connections", "list", f"--location={region}"], project
    )
    for conn in bq_conns:
        name = conn.get("name", "").split("/")[-1]
        if is_ephemeral_prober_resource(name):
            if confirm_delete("BigQuery Connection", name):
                print(f"  Deleting BigQuery connection {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "bigquery",
                        "connections",
                        "delete",
                        name,
                        f"--location={region}",
                        f"--project={project}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 11. Clean API Keys
    print("\n==> 11. Checking API Keys...")
    keys = run_gcloud(["services", "api-keys", "list"], project)
    for key in keys:
        display_name = key.get("displayName", "")
        key_id = key.get("name", "").split("/")[-1]
        if is_ephemeral_prober_resource(display_name):
            if confirm_delete("API Key", f"{display_name} ({key_id})"):
                print(f"  Deleting API Key {display_name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "services",
                        "api-keys",
                        "delete",
                        key_id,
                        f"--project={project}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {display_name}")

    # 12. Clean Dataflow Jobs
    print("\n==> 12. Checking Active Dataflow Jobs...")
    df_jobs = run_gcloud(["dataflow", "jobs", "list", f"--region={region}"], project)
    for dfj in df_jobs:
        job_id = dfj.get("id", "")
        job_name = dfj.get("name", "")
        state = dfj.get("state", "")
        if is_ephemeral_prober_resource(job_name) and state in (
            "JOB_STATE_RUNNING",
            "JOB_STATE_PENDING",
        ):
            if confirm_delete("Dataflow Job", f"{job_name} ({job_id})"):
                print(f"  Cancelling Dataflow Job {job_name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "dataflow",
                        "jobs",
                        "cancel",
                        job_id,
                        f"--region={region}",
                        f"--project={project}",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {job_name}")

    # 13. Clean Orphaned Project IAM Bindings
    print("\n==> 13. Checking Orphaned Project IAM Bindings...")
    policy = run_gcloud(["projects", "get-iam-policy", project], project)
    if isinstance(policy, dict):
        bindings = policy.get("bindings", [])
        for b in bindings:
            role = b.get("role", "")
            members = b.get("members", [])
            for m in members:
                # Matches deleted or active ephemeral service accounts
                sa_name = (
                    m.replace("deleted:serviceAccount:", "")
                    .replace("serviceAccount:", "")
                    .split("@")[0]
                )
                if is_ephemeral_prober_resource(sa_name):
                    if confirm_delete("Orphaned IAM Member", f"{m} ({role})"):
                        print(f"  Removing IAM binding {m} from {role}...")
                        subprocess.run(
                            [
                                "gcloud",
                                "projects",
                                "remove-iam-policy-binding",
                                project,
                                f"--member={m}",
                                f"--role={role}",
                                "--quiet",
                            ],
                            check=False,
                        )
                    else:
                        print(f"  Skipped IAM binding {m}")

    print("\n" + "=" * 80)
    print(" ✔ SAFE INTERACTIVE EPHEMERAL CLEANUP COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    main()
