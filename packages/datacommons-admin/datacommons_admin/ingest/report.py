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
"""Finds, waits for and prints the preprocessor's ingestion report."""

import json
import time
from collections.abc import Callable
from datetime import datetime

import click
from google.cloud import storage
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

# Workflow execution states after which no report will appear.
_DONE_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}

# How long `ingest start --wait` waits for the report.
WAIT_TIMEOUT_SECONDS = 10 * 60


def report_uri(bucket: str, artifacts_path: str, workflow_execution_id: str) -> str:
    """Returns where the preprocessor writes the report for `workflow_execution_id`.

    The workflow runs the preprocessor with OUTPUT_DIR=gs://<bucket>/<artifacts
    path>, and the preprocessor writes its report under
    <OUTPUT_DIR>/datacommons/preprocessor_reports/<execution ID>/.
    """
    return (
        f"gs://{bucket}/{artifacts_path.strip('/')}/datacommons/"
        f"preprocessor_reports/{workflow_execution_id}/ingestion_report.json"
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
    project_id: str | None = None,
    timeout: float = WAIT_TIMEOUT_SECONDS,
    interval: float = 15,
) -> dict:
    """Polls `uri` until the report appears, and returns it.

    `get_state()` returns the workflow execution state. It is read before the
    report, so a run that ended before the read has already written any report
    it was going to write.

    Raises:
      click.ClickException: If the run ends without a report, or on timeout.
    """
    deadline = time.monotonic() + timeout
    while True:
        state = get_state()
        report = read_report(uri, project_id)
        if report is not None:
            return report
        if state in _DONE_STATES:
            raise click.ClickException(
                f"The workflow execution is {state} and wrote no report at {uri}."
            )
        if time.monotonic() >= deadline:
            raise click.ClickException(
                f"Timed out after {timeout / 60:.0f} minutes waiting for the "
                f"report at {uri}."
            )
        time.sleep(interval)


# Node types listed per provenance; the rest are summarized as "N more".
_TOP_NODE_TYPES = 5


def print_report(report: dict, console: Console) -> None:
    """Prints a run header and run errors, then a tree per folder."""
    run = report.get("run", {})
    status = run.get("status") or "UNKNOWN"
    color = "green" if status == "SUCCESS" else "red"
    header = Table.grid(padding=(0, 2))
    header.add_row("Workflow execution ID", run.get("workflowExecutionId") or "-")
    header.add_row("Mode", (run.get("mode") or "-").replace("_", " "))
    header.add_row("Status", f"[bold {color}]{status}[/]")
    header.add_row("Took", _duration(run.get("startTime"), run.get("endTime")))
    console.print(
        Panel(header, title="Ingestion report", border_style=color, expand=False)
    )
    for error in report.get("errors", []):
        console.print(_error(error))
    for folder in report.get("folders", []):
        console.print(_folder_tree(folder))


def _folder_tree(folder: dict) -> Tree:
    """Returns the folder's totals, with one branch per provenance."""
    summary = folder.get("summary", {})
    tree = Tree(
        f"[bold]{folder.get('folderName')}[/]: "
        f"{summary.get('files', {}).get('count', 0):,} files · "
        f"{summary.get('observations', 0):,} observations · "
        f"{summary.get('nodes', {}).get('count', 0):,} nodes",
        guide_style="dim",
    )
    for provenance in folder.get("provenances", []):
        dates = provenance.get("dateRange")
        nodes = provenance.get("nodes", {})
        branch = tree.add(
            f"[bold]{provenance.get('id')}[/]: "
            f"{provenance.get('fileCount', 0):,} files · "
            f"{provenance.get('observations', 0):,} observations"
            + (f" · {dates['min']} – {dates['max']}" if dates else "")
        )
        branch.add(
            f"{nodes.get('count', 0):,} nodes{_top_types(nodes.get('byType', {}))}"
        )
        for error in provenance.get("errors", []):
            branch.add(_error(error))
    return tree


def _error(error: dict) -> str:
    """Returns one report error as "✗ TYPE file: message"."""
    where = f" {error['file']}:" if error["file"] else ""
    return (
        f"[red]✗ {error['errorType']}[/]{escape(where)} {escape(error['errorMessage'])}"
    )


def _top_types(by_type: dict[str, int]) -> str:
    """Returns ": A 4 · B 2 · …" for the most common types, or ""."""
    if not by_type:
        return ""
    ranked = sorted(by_type.items(), key=lambda item: (-item[1], item[0]))
    shown = " · ".join(f"{t} {n:,}" for t, n in ranked[:_TOP_NODE_TYPES])
    more = len(ranked) - _TOP_NODE_TYPES
    return f": {shown}" + (f" · and {more} more" if more > 0 else "")


def _duration(start: str | None, end: str | None) -> str:
    """Returns how long the run took, e.g. "3m 12s", or "-"."""
    if not start or not end:
        return "-"
    seconds = int(
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    )
    return f"{seconds // 60}m {seconds % 60}s" if seconds >= 60 else f"{seconds}s"
