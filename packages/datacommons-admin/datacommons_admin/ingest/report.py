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
"""Finds, waits for and formats the preprocessor's ingestion report."""

import json
import time
from collections.abc import Callable

import click
from google.cloud import storage

# Workflow execution states after which no report will appear.
_FAILED_STATES = {"FAILED", "CANCELLED"}

# How long `ingest start --wait` waits for the report.
WAIT_TIMEOUT_SECONDS = 30 * 60


def report_uri(bucket: str, artifacts_path: str, execution_id: str) -> str:
    """Returns where the preprocessor writes the report for `execution_id`.

    The workflow runs the preprocessor with OUTPUT_DIR=gs://<bucket>/<artifacts
    path>, and the preprocessor writes its report under
    <OUTPUT_DIR>/datacommons/preprocessor_reports/<execution ID>/.
    """
    return (
        f"gs://{bucket}/{artifacts_path.strip('/')}/datacommons/"
        f"preprocessor_reports/{execution_id}/ingestion_report.json"
    )


def read_report(uri: str, project_id: str | None = None) -> dict | None:
    """Returns the report at `uri`, or None if it doesn't exist yet."""
    bucket_name, blob_name = uri.removeprefix("gs://").split("/", 1)
    blob = storage.Client(project=project_id).bucket(bucket_name).blob(blob_name)
    if not blob.exists():
        return None
    return json.loads(blob.download_as_text())


def wait_for_report(
    uri: str,
    get_state: Callable[[], str],
    *,
    view_command: str,
    project_id: str | None = None,
    timeout: float = WAIT_TIMEOUT_SECONDS,
    interval: float = 15,
    state_check_every: int = 4,
) -> dict:
    """Polls `uri` until the report appears, and returns it.

    The report appears as soon as preprocessing ends, before the rest of the
    workflow. Every `state_check_every` polls, `get_state()` (the workflow
    execution state) is checked too, so a run that ends without writing a
    report stops the wait. The timeout error suggests `view_command`.

    Raises:
      click.ClickException: If the run ends without a report, or on timeout.
    """
    deadline = time.monotonic() + timeout
    polls = 0
    while True:
        report = read_report(uri, project_id)
        if report is not None:
            return report
        polls += 1
        if polls % state_check_every == 0:
            state = get_state()
            if state in _FAILED_STATES:
                raise click.ClickException(
                    f"The workflow execution is {state} and wrote no report at {uri}."
                )
            if state == "SUCCEEDED":
                # The report may have been written just before the run ended.
                report = read_report(uri, project_id)
                if report is not None:
                    return report
                raise click.ClickException(
                    f"The workflow execution finished without writing a report at {uri}."
                )
        if time.monotonic() >= deadline:
            raise click.ClickException(
                f"Timed out after {timeout / 60:.0f} minutes waiting for the "
                f"report at {uri}. View it later with: {view_command}"
            )
        time.sleep(interval)


def render_report(report: dict) -> str:
    """Returns a short plain-text summary of the report."""
    run = report.get("run", {})
    lines = [
        f"Run {run.get('workflowExecutionId') or '-'}: "
        f"{run.get('mode', '-')} {run.get('status', '-')}"
    ]
    for folder in report.get("folders", []):
        summary = folder.get("summary", {})
        lines.append(
            f"Folder {folder.get('folderName')}: "
            f"{summary.get('files', {}).get('count', 0)} files, "
            f"{summary.get('provenanceCount', 0)} provenances, "
            f"{summary.get('observations', 0):,} observations, "
            f"{summary.get('nodes', {}).get('count', 0):,} nodes"
        )
        for provenance in folder.get("provenances", []):
            dates = provenance.get("dateRange")
            date_text = f" ({dates['min']} to {dates['max']})" if dates else ""
            lines.append(
                f"  Provenance {provenance.get('id')}: "
                f"{provenance.get('fileCount', 0)} files, "
                f"{provenance.get('observations', 0):,} observations{date_text}, "
                f"{provenance.get('nodes', {}).get('count', 0):,} nodes"
            )
    return "\n".join(lines)
