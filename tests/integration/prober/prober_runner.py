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

"""
Ephemeral DCP Instance Prober Runner.

Production-hardened, resilient orchestrator that:
1. Provisions a dedicated, isolated DCP instance via Terraform.
2. Applies transient retry logic with exponential backoff for GCP API rate limits.
3. Executes full end-to-end integration tests against the fresh instance.
4. Guarantees complete infrastructure teardown via retried 'terraform destroy'.
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
        raise subprocess.CalledProcessError(
            last_proc.returncode, cmd, last_proc.stdout, last_proc.stderr
        )
    return last_proc


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

    # Configure strictly scoped environment to prevent local/inherited leakage
    os.environ.pop("GOOGLE_USER_PROJECT_OVERRIDE", None)
    os.environ.pop("BILLING_PROJECT_ID", None)
    os.environ["GOOGLE_CLOUD_PROJECT"] = args.project
    os.environ["CLOUDSDK_CORE_PROJECT"] = args.project
    os.environ["CLOUDSDK_BILLING_QUOTA_PROJECT"] = args.project
    os.environ["TF_VAR_project_id"] = args.project
    os.environ["TF_VAR_billing_project_id"] = args.project

    # Generate unique instance name for state isolation
    run_id = str(uuid.uuid4())[:8]
    instance_name = f"prober-{run_id}"

    workspace_dir = Path(tempfile.gettempdir()) / instance_name

    print("=" * 80)
    print("STARTING RESILIENT EPHEMERAL DCP PROBER")
    print(f"  Instance Name: {instance_name}")
    print(f"  Project ID:    {args.project}")
    print(f"  Workspace:     {workspace_dir}")
    print("=" * 80)

    # 1. Scaffold Ephemeral Workspace directly from canonical infra/dcp
    source_dir = REPO_ROOT / "infra" / "dcp"
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    shutil.copytree(
        source_dir,
        workspace_dir,
        ignore=shutil.ignore_patterns(
            "backup*", ".terraform*", "*.tfstate*", "*.tfvars*", ".env*"
        ),
    )

    bucket_name = f"tf-state-dcp-prober-{args.project}"

    backend_tf = workspace_dir / "backend.tf"
    backend_tf.write_text(
        f"""
terraform {{
  backend "gcs" {{
    bucket = "{bucket_name}"
    prefix = "ephemeral/{instance_name}"
  }}
}}
"""
    )

    dc_api_key = os.environ.get("DC_API_KEY", "")

    # Load version-controlled prober_overrides.tfvars.template and append dynamic runtime variables
    template_tfvars_path = (
        REPO_ROOT
        / "tests"
        / "integration"
        / "prober"
        / "prober_overrides.tfvars.template"
    )
    if not template_tfvars_path.exists():
        raise FileNotFoundError(
            f"Required prober overrides template not found at: {template_tfvars_path}"
        )
    static_overrides = template_tfvars_path.read_text()

    auto_tfvars = workspace_dir / "prober_overrides.auto.tfvars"
    auto_tfvars.write_text(
        f"""{static_overrides}

# Dynamic Runtime Overrides
instance_name                       = "{instance_name}"
project_id                          = "{args.project}"
auth_google_datacommons_api_key     = "{dc_api_key}"
"""
    )

    deploy_success = False
    destroy_success = True
    test_exit_code = 1

    try:
        # 0. Fetch & install live datacommons-cli from GitHub main at runtime
        print(
            "\n==> Step 0: Fetching live datacommons-cli package from GitHub main branch..."
        )
        try:
            run_cmd_with_retry(
                [
                    "uv",
                    "pip",
                    "install",
                    "--force-reinstall",
                    "git+https://github.com/gmechali/datacommons_platform.git@main#subdirectory=packages/datacommons-cli",
                ],
                cwd=workspace_dir,
                max_attempts=2,
            )
        except Exception as err:
            print(
                f"⚠️  Warning: Failed to fetch live main CLI from GitHub ({err}). Reusing container workspace CLI."
            )

        # 1. Resilient Terraform Init & Apply
        print("\n==> Step 1: Provisioning isolated DCP infrastructure via Terraform...")
        run_cmd_with_retry(
            ["terraform", "init", "-reconfigure"],
            cwd=workspace_dir,
            max_attempts=3,
        )
        run_cmd_with_retry(
            [
                "terraform",
                "apply",
                "-auto-approve",
                f"-var=instance_name={instance_name}",
                f"-var=project_id={args.project}",
            ],
            cwd=workspace_dir,
            max_attempts=3,
            initial_delay=15.0,
        )
        deploy_success = True

        # 3. Execute Integration Test Suite
        print(
            "\n==> Step 2: Executing E2E Integration Suite against provisioned instance..."
        )
        e2e_script = REPO_ROOT / "tests" / "integration" / "run_e2e_tests.py"
        test_res = run_cmd_with_retry(
            [
                "uv",
                "run",
                "python",
                str(e2e_script),
                f"--workspace={workspace_dir}",
                f"--test-config={args.test_config}",
                f"--report-output={args.report_output}",
            ],
            max_attempts=1,
            check=False,
        )
        test_exit_code = test_res.returncode

    finally:
        # 4. Guaranteed Teardown with Retries
        if not args.skip_destroy:
            print("\n==> Step 3: Destroying ephemeral GCP infrastructure...")
            destroy_res = run_cmd_with_retry(
                [
                    "terraform",
                    "destroy",
                    "-auto-approve",
                    f"-var=instance_name={instance_name}",
                    f"-var=project_id={args.project}",
                ],
                cwd=workspace_dir,
                max_attempts=3,
                initial_delay=15.0,
                check=False,
            )
            destroy_success = destroy_res.returncode == 0
            if destroy_res.returncode != 0:
                print(
                    "  ⚠️ Warning: Terraform destroy encountered errors during cleanup."
                )

            if workspace_dir.exists():
                shutil.rmtree(workspace_dir, ignore_errors=True)
        else:
            print(f"\n⚠️ --skip-destroy was set. Workspace retained at: {workspace_dir}")

        overall_passed = deploy_success and (test_exit_code == 0) and destroy_success
        prober_summary = {
            "event_type": "PROBER_EXECUTION_SUMMARY",
            "instance_name": instance_name,
            "status": "PASSED" if overall_passed else "FAILED",
            "status_code": 0 if overall_passed else 1,
            "stages": {
                "deploy": "PASSED" if deploy_success else "FAILED",
                "integration_tests": "PASSED" if test_exit_code == 0 else "FAILED",
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
