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

"""Master E2E Integration Test Runner for Data Commons Platform (DCP)."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_e2e_tests(
    instance: str | None = None,
    project: str = "datcom-dcp",
    workspace: str | None = None,
    suite: str | None = None,
    cli_source: str = "local",
    cli_version: str | None = None,
    dcp_version: str | None = None,
    reuse_data: bool = False,
    workflow_timeout: int = 2400,
    test_config: str | None = None,
    report_output: str | None = None,
    report_json: str | None = None,
    gcs_report_bucket: str | None = None,
    extra_pytest_args: list[str] | None = None,
) -> dict[str, Any]:
    """
    Programmatically runs the integration test suite and returns the structured report object.
    """
    tests_dir = Path(__file__).resolve().parent
    suites_dir = tests_dir / "suites"
    extra_pytest_args = extra_pytest_args or []

    if suite:
        target_path = suites_dir / suite
        if not target_path.exists():
            matches = list(suites_dir.glob(f"*{suite}*"))
            if matches:
                target_path = matches[0]
            else:
                raise ValueError(f"Suite '{suite}' not found under {suites_dir}")
    else:
        target_path = suites_dir

    dest = report_output or report_json or "test_results.json"

    pytest_cmd = [
        "uv",
        "run",
        "pytest",
        str(target_path),
        "-v",
        "-s",
        f"--project={project}",
        f"--cli-source={cli_source}",
        f"--workflow-timeout={workflow_timeout}",
        f"--report-output={dest}",
    ]

    if instance:
        pytest_cmd.append(f"--instance={instance}")
    if workspace:
        pytest_cmd.append(f"--workspace={workspace}")
    if cli_version:
        pytest_cmd.append(f"--cli-version={cli_version}")
    if dcp_version:
        pytest_cmd.append(f"--dcp-version={dcp_version}")
    if reuse_data:
        pytest_cmd.append("--reuse-data")
    if test_config:
        if isinstance(test_config, (list, tuple)):
            pytest_cmd.extend(f"--test-config={tc}" for tc in test_config)
        else:
            pytest_cmd.append(f"--test-config={test_config}")
    if gcs_report_bucket and not dest.startswith("gs://"):
        pytest_cmd.append(f"--gcs-report-bucket={gcs_report_bucket}")

    pytest_cmd.extend(extra_pytest_args)

    repo_root = str(tests_dir.parent.parent)
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root}:{env.get('PYTHONPATH', '')}"

    res = subprocess.run(pytest_cmd, env=env, check=False)

    # Read and return structured report object if saved locally
    if not dest.startswith("gs://"):
        local_path = Path(dest).resolve()
        if local_path.exists():
            try:
                with open(local_path, encoding="utf-8") as f:
                    report_data = json.load(f)
                if res.returncode != 0:
                    report_data["status"] = "FAILED"
                return report_data
            except Exception:
                pass

    if res.returncode != 0:
        return {
            "status": "FAILED",
            "report_destination": dest,
            "error": "pytest run failed",
        }

    return {"status": "COMPLETED", "report_destination": dest}


def main():
    parser = argparse.ArgumentParser(
        description="Data Commons Platform (DCP) Integration Test Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--instance",
        type=str,
        default=None,
        help="Target testbed instance name (e.g. testbed-1)",
    )
    parser.add_argument(
        "--project", type=str, default="datcom-dcp", help="GCP Project ID"
    )
    parser.add_argument(
        "--workspace", type=str, default=None, help="Path to local terraform workspace"
    )
    parser.add_argument(
        "--suite",
        type=str,
        default=None,
        help="Specific suite to run (e.g. 01_ingestion, 03_serving_api)",
    )
    parser.add_argument(
        "--cli-source",
        type=str,
        default="local",
        help="CLI package source ('local', 'git', 'testpypi', 'pypi', or git+ URL)",
    )
    parser.add_argument(
        "--cli-version",
        type=str,
        default=None,
        help="CLI package version tag (for testpypi/pypi)",
    )
    parser.add_argument(
        "--dcp-version",
        type=str,
        default=None,
        help="DCP platform release version (e.g. latest, v1.1.2, dcp-stable)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="dev",
        choices=["dev", "postsubmit", "prober"],
        help="Execution mode",
    )
    parser.add_argument(
        "--reuse-data",
        action="store_true",
        help="Skip ingestion if Spanner already contains data",
    )
    parser.add_argument(
        "--workflow-timeout",
        type=int,
        default=2400,
        help="Ingestion workflow timeout in seconds (default: 2400s / 40min)",
    )
    parser.add_argument(
        "--test-config",
        action="append",
        required=True,
        help="Path or name of dataset specs (e.g. foobar_wages, foobar_education). Can be repeated.",
    )
    parser.add_argument(
        "--report-output",
        type=str,
        default="test_results.json",
        help="Destination to save JSON test report (local path or GCS URI, e.g. gs://bucket/results.json). Default: test_results.json",
    )
    parser.add_argument(
        "--report-json",
        type=str,
        default=None,
        help="(Deprecated: use --report-output) Local report path",
    )
    parser.add_argument(
        "--gcs-report-bucket",
        type=str,
        default=None,
        help="(Deprecated: use --report-output gs://bucket/...) GCS bucket",
    )

    args, extra_pytest_args = parser.parse_known_args()

    report = run_e2e_tests(
        instance=args.instance,
        project=args.project,
        workspace=args.workspace,
        suite=args.suite,
        cli_source=args.cli_source,
        cli_version=args.cli_version,
        dcp_version=args.dcp_version,
        reuse_data=args.reuse_data,
        workflow_timeout=args.workflow_timeout,
        test_config=args.test_config,
        report_output=args.report_output,
        report_json=args.report_json,
        gcs_report_bucket=args.gcs_report_bucket,
        extra_pytest_args=extra_pytest_args,
    )

    status = report.get("status", "FAILED")
    sys.exit(0 if status in ("PASSED", "COMPLETED") else 1)


if __name__ == "__main__":
    main()
