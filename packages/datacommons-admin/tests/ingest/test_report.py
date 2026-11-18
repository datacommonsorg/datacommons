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


def test_wait_for_report_stops_when_the_run_fails_without_a_report() -> None:
    with (
        patch.object(report, "read_report", return_value=None),
        pytest.raises(click.ClickException, match="FAILED and wrote no report"),
    ):
        report.wait_for_report(_URI, lambda: "FAILED", state_check_every=2)


def test_wait_for_report_times_out() -> None:
    with (
        patch.object(report, "read_report", return_value=None),
        pytest.raises(click.ClickException, match="Timed out"),
    ):
        report.wait_for_report(_URI, lambda: "ACTIVE", timeout=0)


def test_render_report_without_folders() -> None:
    rendered = report.render_report(
        {"run": {"workflowExecutionId": "e", "mode": "INGEST", "status": "SUCCESS"}}
    )
    assert rendered == "Run e: INGEST SUCCESS"
