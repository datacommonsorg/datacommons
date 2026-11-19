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
from datetime import datetime

import click
from google.cloud import storage
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

# Workflow execution states after which no report will appear.
_FAILED_STATES = {"FAILED", "CANCELLED"}


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
    project_id: str | None = None,
    timeout: float = 1800,
    interval: float = 15,
    state_check_every: int = 4,
) -> dict:
    """Polls `uri` until the report appears, and returns it.

    The report appears as soon as preprocessing ends, before the rest of the
    workflow. Every `state_check_every` polls, `get_state()` (the workflow
    execution state) is checked too, so a run that fails without writing a
    report stops the wait.

    Raises:
      click.ClickException: If the run fails without a report, or on timeout.
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
        if time.monotonic() >= deadline:
            raise click.ClickException(
                f"Timed out after {timeout:.0f}s waiting for the report at {uri}."
            )
        time.sleep(interval)


# Node types listed per provenance; the rest are summarized as "N more".
_TOP_NODE_TYPES = 5


def print_report(report: dict, console: Console) -> None:
    """Prints the report: a run header, then a table and a tree per folder."""
    run = report.get("run", {})
    status = run.get("status") or "UNKNOWN"
    color = "green" if status == "SUCCESS" else "red"
    header = Table.grid(padding=(0, 2))
    header.add_row("Execution", run.get("workflowExecutionId") or "-")
    header.add_row("Mode", (run.get("mode") or "-").replace("_", " "))
    header.add_row("Status", f"[bold {color}]{status}[/]")
    header.add_row("Took", _duration(run.get("startTime"), run.get("endTime")))
    header.add_row("Folders", ", ".join(run.get("folderNames", [])) or "-")
    console.print(
        Panel(header, title="Ingestion report", border_style=color, expand=False)
    )

    for folder in report.get("folders", []):
        console.print(_folder_table(folder))
        console.print(_provenance_tree(folder))


def _folder_table(folder: dict) -> Table:
    summary = folder.get("summary", {})
    files = summary.get("files", {})
    by_type = ", ".join(f"{n} {t}" for t, n in files.get("byType", {}).items())
    table = Table(title=f"[bold]{folder.get('folderName')}[/]", title_justify="left")
    for column in ["Files", "Provenances", "Observations", "Date range", "Nodes"]:
        table.add_column(column, justify="right")
    table.add_row(
        f"{files.get('count', 0):,}" + (f" ({by_type})" if by_type else ""),
        f"{summary.get('provenanceCount', 0):,}",
        f"{summary.get('observations', 0):,}",
        _date_range([p.get("dateRange") for p in folder.get("provenances", [])]),
        f"{summary.get('nodes', {}).get('count', 0):,}",
    )
    return table


def _provenance_tree(folder: dict) -> Tree:
    tree = Tree("[dim]provenances[/]", guide_style="dim")
    for provenance in folder.get("provenances", []):
        source = provenance.get("sourceId")
        branch = tree.add(
            f"[bold]{provenance.get('id')}[/]"
            + (f" [dim](source: {source})[/]" if source else "")
        )
        branch.add(
            f"{provenance.get('fileCount', 0):,} files · "
            f"{provenance.get('observations', 0):,} observations · "
            f"{_date_range([provenance.get('dateRange')])}"
        )
        nodes = provenance.get("nodes", {})
        branch.add(
            f"{nodes.get('count', 0):,} nodes{_top_types(nodes.get('byType', {}))}"
        )
    return tree


def _top_types(by_type: dict[str, int]) -> str:
    """Returns ": A 4 · B 2 · …" for the most common types, or ""."""
    if not by_type:
        return ""
    ranked = sorted(by_type.items(), key=lambda item: (-item[1], item[0]))
    shown = " · ".join(f"{t} {n:,}" for t, n in ranked[:_TOP_NODE_TYPES])
    more = len(ranked) - _TOP_NODE_TYPES
    return f": {shown}" + (f" · and {more} more" if more > 0 else "")


def _date_range(ranges: list[dict | None]) -> str:
    """Returns "min – max" over `ranges`, or "-" if none has dates."""
    dated = [r for r in ranges if r]
    if not dated:
        return "-"
    return f"{min(r['min'] for r in dated)} – {max(r['max'] for r in dated)}"


def _duration(start: str | None, end: str | None) -> str:
    """Returns how long the run took, e.g. "3m 12s", or "-"."""
    if not start or not end:
        return "-"
    seconds = int(
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    )
    return f"{seconds // 60}m {seconds % 60}s" if seconds >= 60 else f"{seconds}s"
