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

"""Safe interactive script to clean up ALL 13 GCP resource types provisioned by DCP prober in datcom-dcp."""

import json
import subprocess

PROJECT = "datcom-dcp"
REGION = "us-central1"


def run_gcloud(args):
    res = subprocess.run(
        ["gcloud"] + args + ["--project", PROJECT, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        print(f"Warning: gcloud {' '.join(args)} failed: {res.stderr}")
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
    print(
        "================================================================================"
    )
    print(f"SAFE INTERACTIVE EXHAUSTIVE PROBER RESOURCE CLEANUP FOR PROJECT: {PROJECT}")
    print(
        "================================================================================"
    )

    # 1. Clean GCS Buckets
    print("\n==> 1. Checking GCS Buckets...")
    buckets_output = subprocess.run(
        [
            "gcloud",
            "storage",
            "buckets",
            "list",
            f"--project={PROJECT}",
            "--format=json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if buckets_output.returncode == 0:
        buckets = json.loads(buckets_output.stdout)
        for b in buckets:
            name = b.get("name", "")
            if name.startswith("prober-") and "-dc-artifacts-" in name:
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
    secrets = run_gcloud(["secrets", "list"])
    for s in secrets:
        name = s.get("name", "").split("/")[-1]
        if name.startswith("prober-") and name != "dcp-prober-tfvars":
            if confirm_delete("Secret", name):
                print(f"  Deleting secret {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "secrets",
                        "delete",
                        name,
                        f"--project={PROJECT}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 3. Clean Cloud Run Services
    print("\n==> 3. Checking Cloud Run Services...")
    services = run_gcloud(["run", "services", "list", f"--region={REGION}"])
    for svc in services:
        name = svc.get("metadata", {}).get("name", "")
        if name.startswith("prober-") and name != "dcp-prober":
            if confirm_delete("Cloud Run Service", name):
                print(f"  Deleting Cloud Run service {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "run",
                        "services",
                        "delete",
                        name,
                        f"--project={PROJECT}",
                        f"--region={REGION}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 4. Clean Cloud Run Jobs
    print("\n==> 4. Checking Cloud Run Jobs...")
    jobs = run_gcloud(["run", "jobs", "list", f"--region={REGION}"])
    for job in jobs:
        name = job.get("metadata", {}).get("name", "")
        if name.startswith("prober-") and name != "dcp-prober":
            if confirm_delete("Cloud Run Job", name):
                print(f"  Deleting Cloud Run Job {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "run",
                        "jobs",
                        "delete",
                        name,
                        f"--project={PROJECT}",
                        f"--region={REGION}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 5. Clean Cloud Workflows
    print("\n==> 5. Checking Cloud Workflows...")
    workflows = run_gcloud(["workflows", "list", f"--location={REGION}"])
    for wf in workflows:
        name = wf.get("name", "").split("/")[-1]
        if name.startswith("prober-"):
            if confirm_delete("Cloud Workflow", name):
                print(f"  Deleting Cloud Workflow {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "workflows",
                        "delete",
                        name,
                        f"--project={PROJECT}",
                        f"--location={REGION}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 6. Clean Cloud Spanner Instances
    print("\n==> 6. Checking Cloud Spanner Instances...")
    spanner_instances = run_gcloud(["spanner", "instances", "list"])
    for inst in spanner_instances:
        name = inst.get("name", "").split("/")[-1]
        if name.startswith("prober-"):
            if confirm_delete("Spanner Instance", name):
                print(f"  Deleting Spanner Instance {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "spanner",
                        "instances",
                        "delete",
                        name,
                        f"--project={PROJECT}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 7. Clean MemoryStore Redis Instances
    print("\n==> 7. Checking MemoryStore Redis Instances...")
    redis_instances = run_gcloud(["redis", "instances", "list", f"--region={REGION}"])
    for inst in redis_instances:
        name = inst.get("name", "").split("/")[-1]
        if name.startswith("prober-"):
            if confirm_delete("Redis Instance", name):
                print(f"  Deleting Redis Instance {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "redis",
                        "instances",
                        "delete",
                        name,
                        f"--region={REGION}",
                        f"--project={PROJECT}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 8. Clean Serverless VPC Access Connectors
    print("\n==> 8. Checking Serverless VPC Access Connectors...")
    connectors = run_gcloud(
        ["compute", "vpc-access", "connectors", "list", f"--region={REGION}"]
    )
    for conn in connectors:
        name = conn.get("name", "").split("/")[-1]
        if name.startswith("prober-") or "-dc-vpc-conn" in name:
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
                        f"--region={REGION}",
                        f"--project={PROJECT}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 9. Clean Service Accounts
    print("\n==> 9. Checking Service Accounts...")
    sas = run_gcloud(["iam", "service-accounts", "list"])
    for sa in sas:
        email = sa.get("email", "")
        if (
            email.startswith("prober-")
            and email != "dcp-prober-sa@datcom-dcp.iam.gserviceaccount.com"
        ):
            if confirm_delete("Service Account", email):
                print(f"  Deleting Service Account {email}...")
                subprocess.run(
                    [
                        "gcloud",
                        "iam",
                        "service-accounts",
                        "delete",
                        email,
                        f"--project={PROJECT}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {email}")

    # 10. Clean BigQuery Connections
    print("\n==> 10. Checking BigQuery Connections...")
    bq_conns = run_gcloud(["bigquery", "connections", "list", f"--location={REGION}"])
    for conn in bq_conns:
        name = conn.get("name", "").split("/")[-1]
        if name.startswith(("prober_", "prober-")):
            if confirm_delete("BigQuery Connection", name):
                print(f"  Deleting BigQuery connection {name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "bigquery",
                        "connections",
                        "delete",
                        name,
                        f"--location={REGION}",
                        f"--project={PROJECT}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {name}")

    # 11. Clean API Keys
    print("\n==> 11. Checking API Keys...")
    keys = run_gcloud(["services", "api-keys", "list"])
    for key in keys:
        display_name = key.get("displayName", "")
        key_id = key.get("name", "").split("/")[-1]
        if display_name.startswith("prober-"):
            if confirm_delete("API Key", f"{display_name} ({key_id})"):
                print(f"  Deleting API Key {display_name}...")
                subprocess.run(
                    [
                        "gcloud",
                        "services",
                        "api-keys",
                        "delete",
                        key_id,
                        f"--project={PROJECT}",
                        "--quiet",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {display_name}")

    # 12. Clean Dataflow Jobs
    print("\n==> 12. Checking Active Dataflow Jobs...")
    df_jobs = run_gcloud(["dataflow", "jobs", "list", f"--region={REGION}"])
    for dfj in df_jobs:
        job_id = dfj.get("id", "")
        job_name = dfj.get("name", "")
        state = dfj.get("state", "")
        if job_name.startswith("prober-") and state in (
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
                        f"--region={REGION}",
                        f"--project={PROJECT}",
                    ],
                    check=False,
                )
            else:
                print(f"  Skipped {job_name}")
    # 13. Clean Orphaned Project IAM Bindings
    print("\n==> 13. Checking Orphaned Project IAM Bindings...")
    policy_output = subprocess.run(
        ["gcloud", "projects", "get-iam-policy", PROJECT, "--format=json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if policy_output.returncode == 0:
        policy = json.loads(policy_output.stdout)
        bindings = policy.get("bindings", [])
        for b in bindings:
            role = b.get("role", "")
            members = b.get("members", [])
            for m in members:
                if m.startswith("deleted:serviceAccount:prober-") or (
                    m.startswith("serviceAccount:prober-")
                    and m
                    != "serviceAccount:dcp-prober-sa@datcom-dcp.iam.gserviceaccount.com"
                ):
                    if confirm_delete("Orphaned IAM Member", f"{m} ({role})"):
                        print(f"  Removing IAM binding {m} from {role}...")
                        subprocess.run(
                            [
                                "gcloud",
                                "projects",
                                "remove-iam-policy-binding",
                                PROJECT,
                                f"--member={m}",
                                f"--role={role}",
                                "--quiet",
                            ],
                            check=False,
                        )
                    else:
                        print(f"  Skipped IAM binding {m}")

    print(
        "\n================================================================================"
    )
    print(" ✔ SAFE INTERACTIVE EXHAUSTIVE CLEANUP COMPLETE!")
    print(
        "================================================================================"
    )


if __name__ == "__main__":
    main()
