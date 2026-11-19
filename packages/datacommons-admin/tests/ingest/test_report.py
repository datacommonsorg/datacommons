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

from unittest.mock import patch

import click
import pytest
from datacommons_admin.ingest import report
from rich.console import Console

_URI = "gs://b/p/datacommons/preprocessor_reports/e/ingestion_report.json"


def test_report_uri_follows_the_preprocessor_output_layout() -> None:
    assert report.report_uri("b", "/p/", "e") == _URI


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("datacommons_admin.ingest.report.time.sleep"):
        yield


def test_wait_for_report_returns_as_soon_as_the_report_exists() -> None:
    with patch.object(report, "read_report", side_effect=[None, None, {"run": {}}]):
        assert report.wait_for_report(_URI, lambda: "ACTIVE") == {"run": {}}


def test_wait_for_report_returns_a_report_written_just_before_the_run_ended() -> None:
    with patch.object(report, "read_report", return_value={"run": {}}):
        assert report.wait_for_report(_URI, lambda: "SUCCEEDED") == {"run": {}}


@pytest.mark.parametrize("state", ["SUCCEEDED", "FAILED", "CANCELLED"])
def test_wait_for_report_stops_when_the_run_ends_without_a_report(state: str) -> None:
    with (
        patch.object(report, "read_report", return_value=None),
        pytest.raises(click.ClickException, match=f"{state} and wrote no report"),
    ):
        report.wait_for_report(_URI, lambda: state)


def test_wait_for_report_times_out() -> None:
    with (
        patch.object(report, "read_report", return_value=None),
        pytest.raises(click.ClickException, match="Timed out"),
    ):
        report.wait_for_report(_URI, lambda: "ACTIVE", timeout=0)


def _printed(found: dict) -> str:
    console = Console(record=True, width=120)
    report.print_report(found, console)
    return console.export_text()


def test_print_report_shows_folder_and_provenance_totals() -> None:
    printed = _printed(
        {
            "run": {
                "workflowExecutionId": "e",
                "mode": "DRY_RUN",
                "status": "SUCCESS",
                "startTime": "2026-11-18T19:40:05Z",
                "endTime": "2026-11-18T19:43:17Z",
                "folderNames": ["oecd"],
            },
            "folders": [
                {
                    "folderName": "oecd",
                    "summary": {
                        "files": {"count": 3, "byType": {"csv": 2, "mcf": 1}},
                        "provenanceCount": 1,
                        "observations": 4000000,
                        "nodes": {"count": 28},
                    },
                    "provenances": [
                        {
                            "id": "oecdProv",
                            "sourceId": "oecdSource",
                            "fileCount": 3,
                            "observations": 4000000,
                            "dateRange": {"min": "2005", "max": "2021"},
                            "nodes": {
                                "count": 28,
                                "byType": {f"Type{i}": i + 1 for i in range(7)},
                            },
                            "errors": [],
                        }
                    ],
                }
            ],
            "errors": [],
        }
    )

    assert "DRY RUN" in printed
    assert "3m 12s" in printed
    assert "oecd: 3 files · 4,000,000 observations · 28 nodes" in printed
    assert "oecdProv: 3 files · 4,000,000 observations · 2005 – 2021" in printed
    # The five most common types, then the rest.
    assert "Type6 7 · Type5 6 · Type4 5 · Type3 4 · Type2 3 · and 2 more" in printed
    assert "✗" not in printed


def test_print_report_without_folders() -> None:
    printed = _printed({"run": {"mode": "INGEST", "status": "FAILURE"}})
    assert "FAILURE" in printed
    assert "INGEST" in printed


def test_print_report_shows_run_errors_under_the_header() -> None:
    printed = _printed(
        {
            "run": {"mode": "INGEST", "status": "FAILURE"},
            "errors": [
                {
                    "file": "",
                    "errorType": "INVALID_CONFIGURATION",
                    "problemColumns": [],
                    "errorMessage": "Unknown key(s) in config.json: ['x']",
                }
            ],
        }
    )
    assert "✗ INVALID_CONFIGURATION Unknown key(s) in config.json: ['x']" in printed
    assert printed.index("Ingestion report") < printed.index("INVALID_CONFIGURATION")


def test_print_report_shows_provenance_errors_under_the_provenance() -> None:
    printed = _printed(
        {
            "run": {"mode": "DRY_RUN", "status": "FAILURE"},
            "folders": [
                {
                    "folderName": "oecd",
                    "provenances": [
                        {
                            "id": "oecdProv",
                            "errors": [
                                {
                                    "file": "data.csv",
                                    "errorType": "UNMAPPED_COLUMNS",
                                    "problemColumns": ["notes"],
                                    "errorMessage": "Unmapped columns: ['notes']",
                                }
                            ],
                        }
                    ],
                }
            ],
            "errors": [],
        }
    )
    assert "✗ UNMAPPED_COLUMNS data.csv: Unmapped columns: ['notes']" in printed
    assert printed.index("oecdProv") < printed.index("UNMAPPED_COLUMNS")
