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

"""Ephemeral DCP Instance Prober Runner.

Production-hardened, resilient orchestrator that executes in 3 distinct phases:
- Phase 1 (Infrastructure Provisioning):
    1. Installs/syncs live datacommons-cli package.
    2. Scaffolds ephemeral workspace via 'datacommons admin init --tf-git-ref main'.
    3. Injects prober variable overrides and executes 'terraform init' & 'terraform apply'.
- Phase 2 (Test Execution):
    1. Executes full end-to-end integration test suite ('run_e2e_tests.py').
- Phase 3 (Teardown in finally):
    1. Executes 'terraform destroy' with retries.
    2. Cleans up temporary workspace.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def run_cmd_with_retry(
    cmd: list[str],
    cwd: Path | None = None,
    max_attempts: int = 3,
    initial_delay: float = 10.0,
    backoff_factor: float = 2.0,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Executes a subprocess command with retries and exponential backoff for resilience."""
    delay = initial_delay
    last_proc = None

    for attempt in range(1, max_attempts + 1):
        print(f"==> [{attempt}/{max_attempts}] Executing: {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False)
        last_proc = proc

        if proc.returncode == 0:
            return proc

        if attempt < max_attempts:
            print(
                f"  ⚠️ Command failed with exit code {proc.returncode}. Retrying in {delay:.1f}s..."
            )
            time.sleep(delay)
            delay *= backoff_factor

    if check and last_proc and last_proc.returncode != 0:
        raise subprocess.CalledProcessError(last_proc.returncode, cmd)
    return last_proc


def provision_infra(
    workspace_dir: Path,
    instance_name: str,
    project_id: str,
    prober_name: str,
    tf_git_ref: str,
    dc_api_key: str,
) -> Path:
    """Phase 1: Provisions isolated DCP infrastructure via 'datacommons admin init' and Terraform."""
    print("\n" + "=" * 80)
    print("PHASE 1: PROVISIONING ISOLATED DCP INFRASTRUCTURE")
    print("=" * 80)

    # Step 0: Ensure live datacommons packages (admin, cli) are installed from GitHub main
    print(
        f"\n==> [Phase 1.0] Ensuring datacommons packages are synced from GitHub @ {tf_git_ref}..."
    )
    try:
        packages_to_install = [
            f"git+https://github.com/datacommonsorg/datacommons.git@{tf_git_ref}#subdirectory=packages/datacommons-admin",
            f"git+https://github.com/datacommonsorg/datacommons.git@{tf_git_ref}#subdirectory=packages/datacommons-cli",
        ]
        run_cmd_with_retry(
            ["uv", "pip", "install", "--force-reinstall", *packages_to_install],
            cwd=workspace_dir,
            max_attempts=2,
        )
    except Exception as err:
        print(
            f"⚠️  Warning: Failed to fetch packages from GitHub ({err}). Reusing container workspace packages."
        )

    # Step 1: Scaffold workspace using official 'datacommons admin init' command
    print(
        f"\n==> [Phase 1.1] Scaffolding workspace via 'datacommons admin init' (ref: {tf_git_ref})..."
    )
    bucket_name = f"tf-state-{prober_name}-{project_id}"
    run_cmd_with_retry(
        [
            "uv",
            "run",
            "--no-sync",
            "datacommons",
            "admin",
            "init",
            f"--project-id={project_id}",
            f"--instance-name={instance_name}",
            f"--tf-git-ref={tf_git_ref}",
            f"--tf-state-bucket={bucket_name}",
            f"--tf-state-prefix=ephemeral/{instance_name}",
            f"--dc-api-key={dc_api_key}",
            "--force",
        ],
        cwd=workspace_dir,
        max_attempts=2,
    )

    # The admin init command scaffolds into workspace_dir / instance_name
    instance_dir = workspace_dir / instance_name
    if not instance_dir.exists():
        raise FileNotFoundError(
            f"Expected scaffolding directory was not created at: {instance_dir}"
        )

    # Step 2: Apply ephemeral prober variable overrides
    print("\n==> [Phase 1.2] Applying ephemeral prober variable overrides...")
    overrides_src = (
        REPO_ROOT
        / "tests"
        / "integration"
        / "prober"
        / "ephemeral_dcp_overrides.tfvars.template"
    )
    if overrides_src.exists():
        shutil.copy(overrides_src, instance_dir / "prober_overrides.auto.tfvars")
    else:
        raise FileNotFoundError(
            f"Required prober overrides template not found at: {overrides_src}"
        )

    # Step 3: Terraform Init & Apply
    print("\n==> [Phase 1.3] Executing Terraform Init & Apply with retry backoff...")
    run_cmd_with_retry(
        ["terraform", "init", "-reconfigure"],
        cwd=instance_dir,
        max_attempts=3,
    )
    run_cmd_with_retry(
        [
            "terraform",
            "apply",
            "-auto-approve",
        ],
        cwd=instance_dir,
        max_attempts=3,
        initial_delay=15.0,
    )

    return instance_dir


def run_tests(
    instance_dir: Path,
    test_config: str,
    report_output: str,
) -> int:
    """Phase 2: Executes full integration test suite against the provisioned instance."""
    print("\n" + "=" * 80)
    print("PHASE 2: EXECUTING E2E INTEGRATION TEST SUITE")
    print("=" * 80)

    e2e_script = REPO_ROOT / "tests" / "integration" / "run_e2e_tests.py"
    test_res = run_cmd_with_retry(
        [
            "uv",
            "run",
            "--no-sync",
            "python",
            str(e2e_script),
            f"--workspace={instance_dir}",
            f"--test-config={test_config}",
            f"--report-output={report_output}",
        ],
        max_attempts=1,
        check=False,
    )
    return test_res.returncode


def teardown_infra(
    instance_dir: Path | None,
    workspace_dir: Path,
    skip_destroy: bool,
) -> bool:
    """Phase 3: Guaranteed teardown and workspace cleanup."""
    print("\n" + "=" * 80)
    print("PHASE 3: INFRASTRUCTURE TEARDOWN & CLEANUP")
    print("=" * 80)

    destroy_success = True
    if instance_dir and instance_dir.exists() and not skip_destroy:
        print("==> [Phase 3.1] Destroying ephemeral GCP infrastructure...")
        destroy_res = run_cmd_with_retry(
            [
                "terraform",
                "destroy",
                "-auto-approve",
            ],
            cwd=instance_dir,
            max_attempts=3,
            initial_delay=10.0,
            check=False,
        )
        destroy_success = destroy_res.returncode == 0
        if not destroy_success:
            print("  ⚠️ Warning: Terraform destroy encountered errors during cleanup.")
    elif skip_destroy:
        print(
            f"==> [Phase 3.1] Skipping 'terraform destroy' (--skip-destroy set). Workspace kept at: {instance_dir}"
        )

    if not skip_destroy and workspace_dir.exists():
        print("==> [Phase 3.2] Cleaning up temporary workspace directory...")
        shutil.rmtree(workspace_dir, ignore_errors=True)

    return destroy_success


def main():
    parser = argparse.ArgumentParser(
        description="Resilient Ephemeral DCP Prober Runner"
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GCP_PROJECT", "datcom-dcp"),
        help="GCP Project ID",
    )
    parser.add_argument(
        "--prober-name",
        default="dcp-prober",
        help="Resource name prefix for the Prober",
    )
    parser.add_argument(
        "--tf-git-ref",
        default="main",
        help="Git ref for module templates (default: main)",
    )
    parser.add_argument(
        "--test-config",
        default="foobar_wages",
        help="Test config dataset spec name",
    )
    parser.add_argument(
        "--report-output",
        default="prober_results.json",
        help="Destination for test results JSON",
    )
    parser.add_argument(
        "--skip-destroy",
        action="store_true",
        help="Skip terraform destroy (for debugging failed runs)",
    )
    args = parser.parse_args()

    def handle_signal(signum, frame):
        print(f"\n⚠️ Received signal {signum}. Triggering emergency teardown...")
        sys.exit(1)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Generate unique instance name for state isolation
    run_id = str(uuid.uuid4())[:8]
    instance_name = f"prober-{run_id}"

    workspace_dir = Path(tempfile.gettempdir()) / instance_name
    workspace_dir.mkdir(parents=True, exist_ok=True)

    dc_api_key = os.environ.get("DC_API_KEY", "")

    print("=" * 80)
    print("STARTING RESILIENT EPHEMERAL DCP PROBER")
    print(f"  Instance Name: {instance_name}")
    print(f"  Project ID:    {args.project}")
    print(f"  Prober Name:   {args.prober_name}")
    print(f"  Git Ref:       {args.tf_git_ref}")
    print(f"  Workspace:     {workspace_dir}")
    print("=" * 80)

    instance_dir = None
    deploy_success = False
    destroy_success = True
    test_exit_code = 1

    try:
        # Phase 1: Provision
        instance_dir = provision_infra(
            workspace_dir=workspace_dir,
            instance_name=instance_name,
            project_id=args.project,
            prober_name=args.prober_name,
            tf_git_ref=args.tf_git_ref,
            dc_api_key=dc_api_key,
        )
        deploy_success = True

        # Phase 2: Execute Test Suite
        test_exit_code = run_tests(
            instance_dir=instance_dir,
            test_config=args.test_config,
            report_output=args.report_output,
        )

    finally:
        # Phase 3: Teardown
        destroy_success = teardown_infra(
            instance_dir=instance_dir,
            workspace_dir=workspace_dir,
            skip_destroy=args.skip_destroy,
        )

        overall_passed = deploy_success and (test_exit_code == 0) and destroy_success
        prober_summary = {
            "event_type": "PROBER_EXECUTION_SUMMARY",
            "instance_name": instance_name,
            "status": "PASSED" if overall_passed else "FAILED",
            "status_code": 0 if overall_passed else 1,
            "stages": {
                "deploy": "PASSED" if deploy_success else "FAILED",
                "integration_tests": ("PASSED" if test_exit_code == 0 else "FAILED"),
                "destroy": "PASSED" if destroy_success else "FAILED",
            },
        }
        # 1. Single-line structured JSON output for Cloud Logging jsonPayload ingestion
        print(json.dumps(prober_summary), flush=True)

        # 2. Formatted human-readable summary
        print("\n" + "=" * 80, flush=True)
        print("PROBER EXECUTION SUMMARY:", flush=True)
        print(json.dumps(prober_summary, indent=2), flush=True)
        print("=" * 80 + "\n", flush=True)

    final_exit = 0 if overall_passed else (test_exit_code if test_exit_code != 0 else 1)
    sys.exit(final_exit)


if __name__ == "__main__":
    main()
