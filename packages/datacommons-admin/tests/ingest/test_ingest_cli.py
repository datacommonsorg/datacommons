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

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from datacommons_admin.admin_cli import admin

_REPORT_URI = (
    "gs://mock-bucket/ingestion/internal/datacommons/preprocessor_reports/"
    "exec-123/ingestion_report.json"
)
_REPORT = {
    "run": {"workflowExecutionId": "exec-123", "mode": "DRY_RUN", "status": "SUCCESS"},
    "folders": [
        {
            "folderName": "oecd",
            "summary": {
                "files": {"count": 2},
                "provenanceCount": 1,
                "observations": 1200,
                "nodes": {"count": 3},
            },
            "provenances": [
                {
                    "id": "oecdProv",
                    "fileCount": 2,
                    "observations": 1200,
                    "dateRange": {"min": "2005", "max": "2021"},
                    "nodes": {"count": 3},
                }
            ],
        }
    ],
}


def _serve_workflows_api(session) -> None:
    """Answers GET calls with an ACTIVE execution; POST still starts exec-123."""
    started = session.request.return_value

    def request(method, url, **kwargs):
        if method == "POST":
            return started
        resp = MagicMock(ok=True, status_code=200)
        resp.json.return_value = {"state": "ACTIVE"}
        return resp

    session.request.side_effect = request


def _post_calls(session) -> list:
    return [c for c in session.request.call_args_list if c.args[0] == "POST"]


def _started_argument(session) -> dict:
    """The argument the CLI started the workflow with."""
    (post,) = _post_calls(session)
    return json.loads(post.kwargs["json"]["argument"])


@pytest.mark.usefixtures("mock_terraform_ingest", "mock_job_session")
def test_ingest_start_success(
    runner: CliRunner,
) -> None:
    result = runner.invoke(admin, ["ingest", "start", "--imports", "mock-import"])
    assert result.exit_code == 0
    assert "Successfully started ingestion workflow!" in result.output
    assert "Execution ID: exec-123" in result.output
    assert (
        "Execution console link: https://console.cloud.google.com/workflows/workflow/us-central1/mock-workflow/execution/exec-123/summary?project=mock-proj"
        in result.output
    )


def test_ingest_start_fails_without_imports_flag(runner: CliRunner) -> None:
    result = runner.invoke(admin, ["ingest", "start"])
    assert result.exit_code != 0
    assert "Missing option '--imports'" in result.output


@pytest.mark.usefixtures("mock_terraform_ingest")
def test_ingest_show_config_success(runner: CliRunner) -> None:
    result = runner.invoke(admin, ["ingest", "show-config"])
    assert result.exit_code == 0
    assert "Current ingestion job configuration:" in result.output
    assert "PROJECT_ID: mock-proj" in result.output
    assert "REGION: us-central1" in result.output
    assert "GCS_BUCKET: mock-bucket" in result.output


@pytest.mark.usefixtures("mock_terraform_spanner")
def test_ingest_show_config_marks_missing_outputs_unset(runner: CliRunner) -> None:
    result = runner.invoke(admin, ["ingest", "show-config"])
    assert result.exit_code == 0
    assert "GCP_SPANNER_INSTANCE_ID: mock-instance" in result.output
    assert "GCP_SPANNER_DATABASE_NAME: mock-db" in result.output
    assert "GCS_BUCKET: [UNSET]" in result.output


@pytest.mark.usefixtures("mock_terraform_ingest")
def test_ingest_start_with_imports_success(
    mock_job_session,
    runner: CliRunner,
) -> None:
    result = runner.invoke(admin, ["ingest", "start", "--imports", "oecd,doubleup"])
    assert result.exit_code == 0
    assert "Successfully started ingestion workflow!" in result.output

    expected_arg = {
        "imports": ["oecd", "doubleup"],
        "mode": "INGEST",
    }

    # Verify the API was called with the correct argument
    (post,) = _post_calls(mock_job_session)
    assert post.kwargs["timeout"] == 300
    assert _started_argument(mock_job_session) == expected_arg


@pytest.mark.usefixtures("mock_terraform_ingest")
def test_ingest_start_dry_run_sends_dry_run_mode(
    runner: CliRunner, mock_job_session
) -> None:
    _serve_workflows_api(mock_job_session)
    result = runner.invoke(admin, ["ingest", "start", "--imports", "oecd", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert _started_argument(mock_job_session) == {
        "imports": ["oecd"],
        "mode": "DRY_RUN",
    }


@pytest.mark.usefixtures("mock_terraform_ingest")
def test_ingest_start_dry_run_without_wait_prints_the_view_hint(
    runner: CliRunner, mock_job_session
) -> None:
    _serve_workflows_api(mock_job_session)
    with patch("datacommons_admin.ingest.report.read_report") as read:
        result = runner.invoke(
            admin, ["ingest", "start", "--imports", "oecd", "--dry-run"]
        )

    assert result.exit_code == 0, result.output
    assert (
        "The ingestion summary will be ready when preprocessing finishes. "
        "View it with: datacommons admin ingest view --workflow_id=exec-123"
    ) in result.output
    assert f"The report will be written to: {_REPORT_URI}" in result.output
    read.assert_not_called()


@pytest.mark.usefixtures("mock_terraform_ingest")
def test_ingest_start_dry_run_with_wait_prints_the_report(
    runner: CliRunner, mock_job_session
) -> None:
    _serve_workflows_api(mock_job_session)
    with patch(
        "datacommons_admin.ingest.report.read_report", return_value=_REPORT
    ) as read:
        result = runner.invoke(
            admin, ["ingest", "start", "--imports", "oecd", "--dry-run", "--wait"]
        )

    assert result.exit_code == 0, result.output
    read.assert_called_with(_REPORT_URI, "mock-proj")
    assert "DRY RUN" in result.output
    assert "1,200 observations · 2005 – 2021" in result.output


@pytest.mark.usefixtures("mock_terraform_ingest")
def test_ingest_start_with_wait_prints_the_report(
    runner: CliRunner, mock_job_session
) -> None:
    _serve_workflows_api(mock_job_session)
    ingested = {**_REPORT, "run": {**_REPORT["run"], "mode": "INGEST"}}
    with patch(
        "datacommons_admin.ingest.report.read_report", return_value=ingested
    ) as read:
        result = runner.invoke(
            admin, ["ingest", "start", "--imports", "oecd", "--wait"]
        )

    assert result.exit_code == 0, result.output
    read.assert_called_with(_REPORT_URI, "mock-proj")
    assert "INGEST" in result.output


@pytest.mark.usefixtures("mock_terraform_ingest")
def test_ingest_start_without_wait_does_not_poll(
    runner: CliRunner, mock_job_session
) -> None:
    with patch("datacommons_admin.ingest.report.read_report") as read:
        result = runner.invoke(admin, ["ingest", "start", "--imports", "oecd"])

    assert result.exit_code == 0, result.output
    assert _started_argument(mock_job_session)["mode"] == "INGEST"
    assert "The report will be written to" not in result.output
    read.assert_not_called()
    assert mock_job_session.request.call_count == 1


@pytest.mark.usefixtures("mock_terraform_ingest", "mock_job_session")
def test_ingest_view_prints_the_report(runner: CliRunner) -> None:
    with patch("datacommons_admin.ingest.report.read_report", return_value=_REPORT):
        result = runner.invoke(admin, ["ingest", "view", "--workflow_id=exec-123"])

    assert result.exit_code == 0, result.output
    assert "exec-123" in result.output
    assert f"Full report: {_REPORT_URI}" in result.output


@pytest.mark.usefixtures("mock_terraform_ingest", "mock_job_session")
def test_ingest_view_without_a_report_fails(runner: CliRunner) -> None:
    with patch("datacommons_admin.ingest.report.read_report", return_value=None):
        result = runner.invoke(admin, ["ingest", "view", "--workflow_id=exec-123"])

    assert result.exit_code != 0
    assert (
        f"No ingestion report found at {_REPORT_URI}. The run may still be "
        "preprocessing, may have failed before writing a report, or the "
        "workflow ID may be wrong."
    ) in result.output


@pytest.mark.usefixtures("mock_terraform_ingest", "mock_job_session")
def test_ingest_view_of_a_failed_run_exits_with_an_error(runner: CliRunner) -> None:
    failed = {**_REPORT, "run": {**_REPORT["run"], "status": "FAILURE"}}
    with patch("datacommons_admin.ingest.report.read_report", return_value=failed):
        result = runner.invoke(admin, ["ingest", "view", "--workflow_id=exec-123"])

    assert result.exit_code == 1
    assert "FAILURE" in result.output
