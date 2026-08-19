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

import os
import re
import subprocess
from dataclasses import dataclass

from tests.integration.core.target import ArtifactConfig


@dataclass
class CLIResult:
    """Encapsulates the execution result of a Data Commons CLI invocation."""

    command: list[str]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()

    def extract_execution_id(self) -> str | None:
        """Extracts the Cloud Workflow Execution ID from CLI output."""
        # Matches patterns like:
        # Execution ID: 12345678-abcd-...
        # or projects/.../workflows/.../executions/12345678-abcd-...
        match = re.search(r"Execution ID:\s*([a-zA-Z0-9_-]+)", self.output)
        if match:
            return match.group(1).strip()
        match = re.search(r"/executions/([a-zA-Z0-9_-]+)", self.output)
        if match:
            return match.group(1).strip()
        return None


class DatacommonsCLI:
    """Wrapper to execute the Data Commons CLI across various sources."""

    def __init__(self, workspace_dir: str, artifacts: ArtifactConfig | None = None):
        self.workspace_dir = workspace_dir
        self.artifacts = artifacts or ArtifactConfig()

    def run(
        self, args: list[str], env: dict | None = None, timeout: int = 120
    ) -> CLIResult:
        """Executes a datacommons CLI command within the workspace context."""
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        os.makedirs(self.workspace_dir, exist_ok=True)
        cmd = self._build_command(args)
        proc = subprocess.run(
            cmd,
            cwd=self.workspace_dir,
            capture_output=True,
            text=True,
            env=full_env,
            timeout=timeout,
            check=False,
        )

        return CLIResult(
            command=cmd,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def _build_command(self, args: list[str]) -> list[str]:
        cli_source = self.artifacts.cli_source.lower()
        cli_version = self.artifacts.cli_version

        if cli_source == "local":
            # Execute repository CLI package via uv
            return ["uv", "run", "datacommons"] + args

        if cli_source == "testpypi":
            # Execute specific candidate version from TestPyPI
            pkg_spec = (
                f"datacommons-dcp=={cli_version}" if cli_version else "datacommons-dcp"
            )
            return [
                "uv",
                "run",
                "--index-url",
                "https://test.pypi.org/simple/",
                "--extra-index-url",
                "https://pypi.org/simple/",
                "--with",
                pkg_spec,
                "datacommons",
            ] + args

        if cli_source == "pypi":
            # Execute official published version from PyPI
            pkg_spec = (
                f"datacommons-dcp=={cli_version}" if cli_version else "datacommons-dcp"
            )
            return ["uv", "tool", "run", pkg_spec] + args

        # Direct binary invocation fallback
        return [cli_source] + args

    def wait_for_workflow(
        self,
        execution_id: str,
        workflow_name: str,
        project_id: str,
        location: str = "us-central1",
        timeout_seconds: int = 2400,
    ) -> bool:
        """Polls workflow execution via gcloud CLI until completion."""
        import time

        start_time = time.time()
        print(
            f"Waiting for Cloud Workflow execution '{execution_id}' via gcloud CLI..."
        )

        cmd = [
            "gcloud",
            "workflows",
            "executions",
            "describe",
            execution_id,
            f"--workflow={workflow_name}",
            f"--location={location}",
            f"--project={project_id}",
            "--format=value(state)",
        ]

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                raise TimeoutError(
                    f"Workflow execution {execution_id} timed out after {timeout_seconds}s"
                )

            try:
                state = (
                    subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
                    .decode()
                    .strip()
                )
                if state == "SUCCEEDED":
                    return True
                if state in ("FAILED", "CANCELLED"):
                    raise RuntimeError(
                        f"Workflow execution {execution_id} finished with state: {state}"
                    )
            except Exception as e:
                if "finished with state" in str(e) or "timed out" in str(e):
                    raise

            time.sleep(15)
