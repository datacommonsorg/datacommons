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

import datetime
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from google.cloud import storage


@dataclass
class TestCaseResult:
    nodeid: str
    outcome: str  # "passed", "failed", "skipped"
    duration: float
    error_message: str | None = None


@dataclass
class TestRunReport:
    timestamp: str
    target_instance: str
    target_project: str
    test_config: str
    cli_source: str
    cli_version: str
    target_tag: str
    git_commit: str
    main_git_commit: str = "unknown"
    prober_git_commit: str = "unknown"
    artifacts: dict[str, Any] = field(default_factory=dict)
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    duration_seconds: float = 0.0
    results: list[TestCaseResult] = field(default_factory=list)


class TestReporter:
    """Collects and publishes structured JSON test results."""

    def __init__(
        self,
        target_instance: str = "unknown",
        target_project: str = "unknown",
        test_config: str = "default_benchmark",
        cli_source: str = "local",
        cli_version: str | None = None,
        target_tag: str | None = None,
        artifacts: dict[str, Any] | None = None,
    ):
        config_name = Path(test_config).stem if test_config else "benchmark"
        main_sha, prober_sha = self._resolve_git_shas()
        resolved_cli_ver = cli_version or self._auto_detect_cli_version(main_sha)

        self.report = TestRunReport(
            timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
            target_instance=target_instance,
            target_project=target_project,
            test_config=config_name,
            cli_source=cli_source,
            cli_version=resolved_cli_ver,
            target_tag=target_tag or "latest",
            git_commit=main_sha,
            main_git_commit=main_sha,
            prober_git_commit=prober_sha,
            artifacts=artifacts or {},
        )

    def _resolve_git_shas(self) -> tuple[str, str]:
        """Resolves (main_git_commit, prober_git_commit) cleanly."""
        prober_sha = (
            os.environ.get("COMMIT_SHA")
            or os.environ.get("GIT_COMMIT")
            or self._run_cmd(["git", "rev-parse", "HEAD"])
        )
        main_sha = os.environ.get("MAIN_COMMIT_SHA")

        if not main_sha or main_sha == "unknown":
            main_sha = self._run_cmd(
                ["git", "rev-parse", "origin/main"]
            ) or self._run_cmd(["git", "rev-parse", "main"])

            if not main_sha:
                remote_url = os.environ.get(
                    "GIT_REMOTE_URL",
                    "https://github.com/datacommonsorg/datacommons.git",
                )
                out = self._run_cmd(
                    ["git", "ls-remote", remote_url, "main"], timeout=5
                )
                parts = out.split()
                main_sha = parts[0] if parts else ""

        return main_sha or "unknown", prober_sha or "unknown"

    def _auto_detect_cli_version(self, main_sha: str) -> str:
        out = self._run_cmd(["datacommons", "--version"])
        match = (
            re.search(r"version\s+([0-9a-zA-Z\.\-]+)", out, re.IGNORECASE)
            if out
            else None
        )
        ver_str = match.group(1) if match else (out or "0.0.0")

        short_sha = main_sha[:8] if main_sha and main_sha != "unknown" else ""
        return (
            f"{ver_str} ({short_sha})" if short_sha and "(" not in ver_str else ver_str
        )

    def _run_cmd(self, cmd: list[str], timeout: int = 5) -> str:
        try:
            return (
                subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=timeout)
                .decode()
                .strip()
            )
        except Exception:
            return ""

    def generate_filename(self) -> str:
        """
        Generates a timestamp-prefixed, context-rich filename that sorts chronologically:
        e.g. 20260819T150116Z_testbed-1_foobar_wages+foobar_education_a37dc799_PASSED.json
        """
        try:
            dt = datetime.datetime.fromisoformat(
                self.report.timestamp.replace("Z", "+00:00")
            )
            ts_str = dt.strftime("%Y%m%dT%H%M%SZ")
        except Exception:
            ts_str = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")

        instance = self.report.target_instance or "unknown"
        datasets = self.report.test_config or "benchmark"
        commit = self.report.git_commit[:8] if self.report.git_commit else "latest"
        status = (
            "PASSED"
            if (self.report.failed_tests == 0 and self.report.total_tests > 0)
            else "FAILED"
        )
        clean_datasets = re.sub(r"[^a-zA-Z0-9_\-+]", "_", datasets)

        return f"{ts_str}_{instance}_{clean_datasets}_{commit}_{status}.json"

    def set_artifacts(self, artifacts: dict[str, Any]):
        """Sets or updates the deployed artifact images in the report."""
        excluded = {"cli_source", "cli_version", "target_tag"}
        self.report.artifacts = {
            k: v for k, v in artifacts.items() if k not in excluded and v is not None
        }

    def add_result(
        self,
        nodeid: str,
        outcome: str,
        duration: float,
        error_message: str | None = None,
    ):
        self.report.total_tests += 1
        if outcome == "passed":
            self.report.passed_tests += 1
        elif outcome == "failed":
            self.report.failed_tests += 1
        elif outcome == "skipped":
            self.report.skipped_tests += 1

        self.report.results.append(
            TestCaseResult(
                nodeid=nodeid,
                outcome=outcome,
                duration=round(duration, 4),
                error_message=error_message,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        status = (
            "PASSED"
            if (self.report.failed_tests == 0 and self.report.total_tests > 0)
            else "FAILED"
        )
        return {
            "status": status,
            "summary": {
                "total": self.report.total_tests,
                "passed": self.report.passed_tests,
                "failed": self.report.failed_tests,
                "skipped": self.report.skipped_tests,
                "duration_seconds": round(self.report.duration_seconds, 2),
            },
            "metadata": {
                "timestamp": self.report.timestamp,
                "target_instance": self.report.target_instance,
                "target_project": self.report.target_project,
                "test_config": self.report.test_config,
                "cli_source": self.report.cli_source,
                "cli_version": self.report.cli_version,
                "target_tag": self.report.target_tag,
                "git_commit": self.report.git_commit,
                "artifacts": self.report.artifacts,
            },
            "tests": [asdict(r) for r in self.report.results],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def save_local(self, output_path: Path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    def save_report(self, destination: str | None = None) -> str:
        """
        Saves the structured report to a local directory/file or to Google Cloud Storage (gs://).
        If a directory path is supplied, it automatically appends the timestamp-sorted descriptive filename.
        """
        dest = (destination or "test_results/").strip()
        filename = self.generate_filename()

        if dest.startswith("gs://"):
            # Format: gs://bucket-name/optional/dir/
            raw = dest[5:].rstrip("/")
            parts = raw.split("/", 1)
            bucket_name = parts[0]
            prefix = parts[1] if len(parts) > 1 and parts[1] else ""

            # Check if destination ends in .json (explicit file) or is a directory
            if dest.endswith(".json"):
                blob_name = prefix
            else:
                blob_name = f"{prefix}/{filename}" if prefix else filename

            try:
                client = storage.Client(project=self.report.target_project)
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                blob.upload_from_string(self.to_json(), content_type="application/json")
                gcs_uri = f"gs://{bucket_name}/{blob_name}"
                print(f"\n[Reporter] ✔ Uploaded machine-readable report to: {gcs_uri}")
                return gcs_uri
            except Exception as e:
                print(
                    f"\n[Reporter] [Warning] Failed to upload test report to GCS ({dest}): {e}"
                )
                fallback = Path("test_results") / filename
                self.save_local(fallback)
                return str(fallback.resolve())
        else:
            p = Path(dest)
            if p.suffix == ".json":
                target_file = p.resolve()
            else:
                target_file = (p / filename).resolve()

            self.save_local(target_file)
            print(
                f"\n[Reporter] ✔ Wrote machine-readable test results to: {target_file}"
            )
            return str(target_file)
