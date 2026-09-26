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

Features & Safety:
------------------
- Tag Scoping: Target a specific prober tag (e.g. 'f0dfed8d') to safely isolate
  resources without touching concurrent testbeds.
- Two-Phase Discovery: Scans and reports an inventory of all discovered resources
  before deleting anything.
- Flexible Deletion Modes: Choose bulk auto-delete ([A]) for tagged batches,
  one-by-one interactive review ([I]), or quit ([Q]).
"""

import argparse
from dataclasses import dataclass
import json
import os
import re
import subprocess
import time
from typing import Callable


@dataclass
class ResourceItem:
    category: str
    resource_type: str
    resource_id: str
    display_info: str
    delete_fn: Callable[[], bool]


def normalize_tag(tag: str | None) -> str | None:
    """Validates and normalizes a prober tag into an 8-character hex string."""
    if not tag:
        return None
    cleaned = tag.strip().lower()
    if not cleaned:
        return None
    if cleaned.startswith("prober-"):
        cleaned = cleaned[len("prober-") :]
    if not re.match(r"^[a-f0-9]{8}$", cleaned):
        raise ValueError(
            f"Invalid prober tag '{tag}'. Expected an 8-character hex string (e.g. 'f0dfed8d' or 'prober-f0dfed8d')."
        )
    return cleaned


def build_matcher(tag: str | None) -> Callable[[str], bool]:
    """Returns a predicate matching resources for the specific tag or any ephemeral prober."""
    if tag:
        prefix = f"prober-{tag}"
        return lambda name: isinstance(name, str) and name.startswith(prefix)
    pattern = re.compile(r"^prober-[a-f0-9]{8}")
    return lambda name: isinstance(name, str) and bool(pattern.match(name))


def run_gcloud(args: list[str], project: str) -> list[dict] | dict:
    """Executes a gcloud CLI command non-interactively and parses the JSON response."""
    env = os.environ.copy()
    env["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    try:
        res = subprocess.run(
            ["gcloud"] + args + ["--project", project, "--format", "json", "--quiet"],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            env=env,
            timeout=30,
        )
        if res.returncode != 0:
            return []
        return json.loads(res.stdout) if res.stdout.strip() else []
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
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
        description="Safe cleanup of orphaned ephemeral prober resources."
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
    parser.add_argument(
        "--tag",
        default=None,
        help="Specific prober tag to clean (e.g. f0dfed8d or prober-f0dfed8d). If omitted, prompts interactively.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Auto-approve bulk deletion of all discovered resources for the specified --tag.",
    )
    args = parser.parse_args()

    project = args.project
    region = args.region

    print("=" * 80)
    print(f"SAFE EPHEMERAL PROBER RESOURCE CLEANUP FOR PROJECT: {project}")
    print("=" * 80)

    # 1. Resolve Tag
    tag = None
    if args.tag:
        try:
            tag = normalize_tag(args.tag)
        except ValueError as e:
            print(f"❌ Error: {e}")
            return
    else:
        try:
            raw_tag = input(
                "\nEnter specific prober tag (e.g. f0dfed8d) or press Enter to scan all ephemeral probers: "
            ).strip()
            if raw_tag:
                tag = normalize_tag(raw_tag)
        except ValueError as e:
            print(f"❌ Error: {e}")
            return
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return

    if tag:
        print(f"\n🎯 Scope locked to prober tag: [prober-{tag}]")
        print(
            "   (Only resources matching this specific prober will be scanned or deleted)"
        )
    else:
        print(
            "\n🔍 Scope: Scanning ALL ephemeral prober resources matching 'prober-[a-f0-9]{8}'..."
        )

    matcher = build_matcher(tag)

    # 2. Phase 1: Discovery Manifest
    print(f"\n==> Scanning 12 GCP resource types in project [{project}]...")
    discovered: list[ResourceItem] = []

    # [1/12] Cloud Run Services
    print("  [1/12] Checking Cloud Run Services...", end="", flush=True)
    services = run_gcloud(["run", "services", "list", f"--region={region}"], project)
    svc_count = 0
    for svc in services:
        name = svc.get("metadata", {}).get("name", "")
        if matcher(name):
            svc_count += 1

            def _make_svc_delete(n=name, p=project, r=region):
                res = subprocess.run(
                    [
                        "gcloud",
                        "run",
                        "services",
                        "delete",
                        n,
                        f"--project={p}",
                        f"--region={r}",
                        "--quiet",
                    ],
                    check=False,
                    capture_output=True,
                )
                return res.returncode == 0

            discovered.append(
                ResourceItem(
                    category="Cloud Run Services",
                    resource_type="Cloud Run Service",
                    resource_id=name,
                    display_info=name,
                    delete_fn=_make_svc_delete,
                )
            )
    print(f" found {svc_count}")

    # [2/12] Cloud Run Jobs
    print("  [2/12] Checking Cloud Run Jobs...", end="", flush=True)
    jobs = run_gcloud(["run", "jobs", "list", f"--region={region}"], project)
    job_count = 0
    for job in jobs:
        name = job.get("metadata", {}).get("name", "")
        if matcher(name):
            job_count += 1

            def _make_job_delete(n=name, p=project, r=region):
                res = subprocess.run(
                    [
                        "gcloud",
                        "run",
                        "jobs",
                        "delete",
                        n,
                        f"--project={p}",
                        f"--region={r}",
                        "--quiet",
                    ],
                    check=False,
                    capture_output=True,
                )
                return res.returncode == 0

            discovered.append(
                ResourceItem(
                    category="Cloud Run Jobs",
                    resource_type="Cloud Run Job",
                    resource_id=name,
                    display_info=name,
                    delete_fn=_make_job_delete,
                )
            )
    print(f" found {job_count}")

    # [3/12] Cloud Workflows
    print("  [3/12] Checking Cloud Workflows...", end="", flush=True)
    workflows = run_gcloud(["workflows", "list", f"--location={region}"], project)
    wf_count = 0
    for wf in workflows:
        name = wf.get("name", "").split("/")[-1]
        if matcher(name):
            wf_count += 1

            def _make_wf_delete(n=name, p=project, r=region):
                res = subprocess.run(
                    [
                        "gcloud",
                        "workflows",
                        "delete",
                        n,
                        f"--project={p}",
                        f"--location={r}",
                        "--quiet",
                    ],
                    check=False,
                    capture_output=True,
                )
                return res.returncode == 0

            discovered.append(
                ResourceItem(
                    category="Cloud Workflows",
                    resource_type="Cloud Workflow",
                    resource_id=name,
                    display_info=name,
                    delete_fn=_make_wf_delete,
                )
            )
    print(f" found {wf_count}")

    # [4/12] Project IAM Bindings
    print("  [4/12] Checking Project IAM Bindings...", end="", flush=True)
    policy = run_gcloud(["projects", "get-iam-policy", project], project)
    iam_count = 0
    if isinstance(policy, dict):
        bindings = policy.get("bindings", [])
        for b in bindings:
            role = b.get("role", "")
            members = b.get("members", [])
            for m in members:
                sa_name = (
                    m.replace("deleted:serviceAccount:", "")
                    .replace("serviceAccount:", "")
                    .split("@")[0]
                )
                if matcher(sa_name):
                    iam_count += 1

                    def _make_iam_delete(mem=m, r=role, p=project):
                        for attempt in range(3):
                            res = subprocess.run(
                                [
                                    "gcloud",
                                    "projects",
                                    "remove-iam-policy-binding",
                                    p,
                                    f"--member={mem}",
                                    f"--role={r}",
                                    "--all",
                                    "--quiet",
                                    "--format=none",
                                ],
                                check=False,
                                capture_output=True,
                                text=True,
                            )
                            if res.returncode == 0:
                                return True
                            stderr = (res.stderr or "").lower()
                            # If binding is already gone or not found under this name
                            if "not found" in stderr:
                                # If member was serviceAccount:..., check if SA was deleted concurrently
                                # and converted to deleted:serviceAccount:...?...
                                if mem.startswith("serviceAccount:"):
                                    pol = run_gcloud(
                                        ["projects", "get-iam-policy", p], p
                                    )
                                    if isinstance(pol, dict):
                                        target_sa = mem.split(":")[1]
                                        for pb in pol.get("bindings", []):
                                            if pb.get("role") == r:
                                                for bm in pb.get("members", []):
                                                    if (
                                                        bm.startswith(
                                                            "deleted:serviceAccount:"
                                                        )
                                                        and target_sa in bm
                                                    ):
                                                        res2 = subprocess.run(
                                                            [
                                                                "gcloud",
                                                                "projects",
                                                                "remove-iam-policy-binding",
                                                                p,
                                                                f"--member={bm}",
                                                                f"--role={r}",
                                                                "--all",
                                                                "--quiet",
                                                                "--format=none",
                                                            ],
                                                            check=False,
                                                            capture_output=True,
                                                            text=True,
                                                        )
                                                        if res2.returncode == 0:
                                                            return True
                                # If not found anywhere, it is already deleted
                                return True
                            # Only retry on concurrent policy update race conditions
                            if "concurrent" in stderr or "conflict" in stderr:
                                time.sleep(0.5 * (attempt + 1))
                                continue
                            return False
                        return False

                    discovered.append(
                        ResourceItem(
                            category="Project IAM Bindings",
                            resource_type="IAM Binding",
                            resource_id=f"{m} ({role})",
                            display_info=f"{m} ({role})",
                            delete_fn=_make_iam_delete,
                        )
                    )
    print(f" found {iam_count}")

    # [5/12] Service Accounts
    print("  [5/12] Checking Service Accounts...", end="", flush=True)
    sas = run_gcloud(["iam", "service-accounts", "list"], project)
    sa_count = 0
    for sa in sas:
        email = sa.get("email", "")
        sa_prefix = email.split("@")[0]
        if matcher(sa_prefix):
            sa_count += 1

            def _make_sa_delete(em=email, p=project):
                res = subprocess.run(
                    [
                        "gcloud",
                        "iam",
                        "service-accounts",
                        "delete",
                        em,
                        f"--project={p}",
                        "--quiet",
                    ],
                    check=False,
                    capture_output=True,
                )
                return res.returncode == 0

            discovered.append(
                ResourceItem(
                    category="Service Accounts",
                    resource_type="Service Account",
                    resource_id=email,
                    display_info=email,
                    delete_fn=_make_sa_delete,
                )
            )
    print(f" found {sa_count}")

    # [6/12] GCS Buckets
    print("  [6/12] Checking GCS Buckets...", end="", flush=True)
    buckets = run_gcloud(["storage", "buckets", "list"], project)
    bucket_count = 0
    for b in buckets:
        name = b.get("name", "")
        if matcher(name):
            bucket_count += 1

            def _make_bucket_delete(n=name):
                res = subprocess.run(
                    ["gcloud", "storage", "rm", "--recursive", f"gs://{n}", "--quiet"],
                    check=False,
                    capture_output=True,
                )
                return res.returncode == 0

            discovered.append(
                ResourceItem(
                    category="GCS Buckets",
                    resource_type="GCS Bucket",
                    resource_id=f"gs://{name}",
                    display_info=f"gs://{name}",
                    delete_fn=_make_bucket_delete,
                )
            )
    print(f" found {bucket_count}")

    # [7/12] Cloud Spanner Instances
    print("  [7/12] Checking Cloud Spanner Instances...", end="", flush=True)
    spanner_instances = run_gcloud(["spanner", "instances", "list"], project)
    spanner_count = 0
    for inst in spanner_instances:
        name = inst.get("name", "").split("/")[-1]
        if matcher(name):
            spanner_count += 1

            def _make_spanner_delete(n=name, p=project):
                # Delete any backups first
                backups = run_gcloud(
                    ["spanner", "backups", "list", f"--instance={n}"], p
                )
                if isinstance(backups, list):
                    for b in backups:
                        if isinstance(b, dict) and b.get("name"):
                            b_name = b["name"].split("/")[-1]
                            subprocess.run(
                                [
                                    "gcloud",
                                    "spanner",
                                    "backups",
                                    "delete",
                                    b_name,
                                    f"--instance={n}",
                                    f"--project={p}",
                                    "--quiet",
                                ],
                                check=False,
                                capture_output=True,
                            )
                res = subprocess.run(
                    [
                        "gcloud",
                        "spanner",
                        "instances",
                        "delete",
                        n,
                        f"--project={p}",
                        "--quiet",
                    ],
                    check=False,
                    capture_output=True,
                )
                return res.returncode == 0

            discovered.append(
                ResourceItem(
                    category="Cloud Spanner Instances",
                    resource_type="Spanner Instance",
                    resource_id=name,
                    display_info=name,
                    delete_fn=_make_spanner_delete,
                )
            )
    print(f" found {spanner_count}")

    # [8/12] MemoryStore Redis Instances
    print("  [8/12] Checking MemoryStore Redis Instances...", end="", flush=True)
    redis_instances = run_gcloud(
        ["redis", "instances", "list", f"--region={region}"], project
    )
    redis_count = 0
    for inst in redis_instances:
        name = inst.get("name", "").split("/")[-1]
        if matcher(name):
            redis_count += 1

            def _make_redis_delete(n=name, p=project, r=region):
                res = subprocess.run(
                    [
                        "gcloud",
                        "redis",
                        "instances",
                        "delete",
                        n,
                        f"--region={r}",
                        f"--project={p}",
                        "--quiet",
                    ],
                    check=False,
                    capture_output=True,
                )
                return res.returncode == 0

            discovered.append(
                ResourceItem(
                    category="MemoryStore Redis Instances",
                    resource_type="Redis Instance",
                    resource_id=name,
                    display_info=name,
                    delete_fn=_make_redis_delete,
                )
            )
    print(f" found {redis_count}")

    # [9/12] Serverless VPC Access Connectors
    print("  [9/12] Checking Serverless VPC Access Connectors...", end="", flush=True)
    connectors = run_gcloud(
        ["compute", "vpc-access", "connectors", "list", f"--region={region}"], project
    )
    conn_count = 0
    for conn in connectors:
        name = conn.get("name", "").split("/")[-1]
        if matcher(name):
            conn_count += 1

            def _make_conn_delete(n=name, p=project, r=region):
                res = subprocess.run(
                    [
                        "gcloud",
                        "compute",
                        "vpc-access",
                        "connectors",
                        "delete",
                        n,
                        f"--region={r}",
                        f"--project={p}",
                        "--quiet",
                    ],
                    check=False,
                    capture_output=True,
                )
                return res.returncode == 0

            discovered.append(
                ResourceItem(
                    category="VPC Connectors",
                    resource_type="VPC Connector",
                    resource_id=name,
                    display_info=name,
                    delete_fn=_make_conn_delete,
                )
            )
    print(f" found {conn_count}")

    # [10/12] BigQuery Connections
    print("  [10/12] Checking BigQuery Connections...", end="", flush=True)
    bq_conns = run_gcloud(
        ["bigquery", "connections", "list", f"--location={region}"], project
    )
    bq_count = 0
    for conn in bq_conns:
        name = conn.get("name", "").split("/")[-1]
        if matcher(name):
            bq_count += 1

            def _make_bq_delete(n=name, p=project, r=region):
                res = subprocess.run(
                    [
                        "gcloud",
                        "bigquery",
                        "connections",
                        "delete",
                        n,
                        f"--location={r}",
                        f"--project={p}",
                        "--quiet",
                    ],
                    check=False,
                    capture_output=True,
                )
                return res.returncode == 0

            discovered.append(
                ResourceItem(
                    category="BigQuery Connections",
                    resource_type="BigQuery Connection",
                    resource_id=name,
                    display_info=name,
                    delete_fn=_make_bq_delete,
                )
            )
    print(f" found {bq_count}")

    # [11/12] API Keys
    print("  [11/12] Checking API Keys...", end="", flush=True)
    keys = run_gcloud(["services", "api-keys", "list"], project)
    keys_count = 0
    for key in keys:
        display_name = key.get("displayName", "")
        key_id = key.get("name", "").split("/")[-1]
        if matcher(display_name):
            keys_count += 1

            def _make_key_delete(k_id=key_id, p=project):
                res = subprocess.run(
                    [
                        "gcloud",
                        "services",
                        "api-keys",
                        "delete",
                        k_id,
                        f"--project={p}",
                        "--quiet",
                    ],
                    check=False,
                    capture_output=True,
                )
                return res.returncode == 0

            discovered.append(
                ResourceItem(
                    category="API Keys",
                    resource_type="API Key",
                    resource_id=key_id,
                    display_info=f"{display_name} ({key_id})",
                    delete_fn=_make_key_delete,
                )
            )
    print(f" found {keys_count}")

    # [12/12] Secret Manager Secrets
    print("  [12/12] Checking Secret Manager Secrets...", end="", flush=True)
    secrets = run_gcloud(["secrets", "list"], project)
    sec_count = 0
    for s in secrets:
        name = s.get("name", "").split("/")[-1]
        if matcher(name):
            sec_count += 1

            def _make_sec_delete(n=name, p=project):
                res = subprocess.run(
                    ["gcloud", "secrets", "delete", n, f"--project={p}", "--quiet"],
                    check=False,
                    capture_output=True,
                )
                return res.returncode == 0

            discovered.append(
                ResourceItem(
                    category="Secret Manager Secrets",
                    resource_type="Secret",
                    resource_id=name,
                    display_info=name,
                    delete_fn=_make_sec_delete,
                )
            )
    print(f" found {sec_count}")

    # 3. Phase 2: Inventory Presentation
    total = len(discovered)
    target_label = f"FOR PROBER TAG [{tag}]" if tag else "ACROSS ALL EPHEMERAL PROBERS"

    if total == 0:
        print("\n" + "=" * 80)
        print(f" ✔ NO ORPHANED RESOURCES FOUND {target_label} IN PROJECT: {project}")
        print("=" * 80)
        return

    # Group by category for structured summary
    grouped: dict[str, list[ResourceItem]] = {}
    for item in discovered:
        grouped.setdefault(item.category, []).append(item)

    print("\n" + "=" * 80)
    print(f"DISCOVERED ORPHANED RESOURCES {target_label} (Total: {total})")
    print("=" * 80)
    for cat_name, items in grouped.items():
        print(f"\n  📁 {cat_name} ({len(items)}):")
        for it in items:
            print(f"    • {it.display_info}")
    print("\n" + "=" * 80)

    # 4. Phase 3: Confirmation & Execution Mode
    mode = "quit"
    if args.yes:
        if not tag:
            print(
                "\n❌ Safety Guard: --yes/-y flag requires an explicit --tag to prevent accidental bulk-wipe."
            )
            return
        mode = "all"
    else:
        print("\nSelect Deletion Mode:")
        if tag:
            print(
                f"  [A] Delete ALL {total} resources for prober [{tag}] at once (auto-approve)"
            )
        else:
            print(
                f"  [A] Delete ALL {total} resources across ALL probers (requires typing 'DELETE ALL')"
            )
        print("  [I] Review and delete interactively one-by-one [y/N]")
        print("  [Q] Quit / Cancel (do not delete anything)")

        try:
            choice = input("\nAction [A/I/Q] (default: Q): ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n  Cancelled.")
            return

        if choice == "A":
            if not tag:
                try:
                    confirm_str = input(
                        f"\n  ⚠️  WARNING: You are about to delete {total} resources across MULTIPLE probers!\n"
                        f"  Type 'DELETE ALL' to confirm: "
                    ).strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n  Cancelled.")
                    return
                if confirm_str != "DELETE ALL":
                    print("  Cancelled. No resources were deleted.")
                    return
            mode = "all"
        elif choice == "I":
            mode = "interactive"
        else:
            print("  Cancelled. No resources were deleted.")
            return

    # 5. Phase 4: Execution
    if mode == "all":
        print(f"\n🚀 Bulk deleting {total} resources...")
        success_count = 0
        fail_count = 0
        for item in discovered:
            print(
                f"  Deleting {item.resource_type}: {item.display_info}...",
                end="",
                flush=True,
            )
            ok = item.delete_fn()
            if ok:
                print(" ✔ Done")
                success_count += 1
            else:
                print(" ❌ Error")
                fail_count += 1
        print("\n" + "=" * 80)
        print(
            f" ✔ BULK CLEANUP COMPLETE: {success_count} deleted, {fail_count} failed."
        )
        print("=" * 80)

    elif mode == "interactive":
        print(f"\nReviewing {total} resources one-by-one...")
        success_count = 0
        skipped_count = 0
        for item in discovered:
            if confirm_delete(item.resource_type, item.display_info):
                print(
                    f"    Deleting {item.resource_type}: {item.display_info}...",
                    end="",
                    flush=True,
                )
                ok = item.delete_fn()
                if ok:
                    print(" ✔ Done")
                    success_count += 1
                else:
                    print(" ❌ Error")
            else:
                print(f"    Skipped {item.display_info}")
                skipped_count += 1
        print("\n" + "=" * 80)
        print(
            f" ✔ INTERACTIVE CLEANUP COMPLETE: {success_count} deleted, {skipped_count} skipped."
        )
        print("=" * 80)


if __name__ == "__main__":
    main()
