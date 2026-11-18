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


def _workflow_get(source: str = "... DRY_RUN ...", state: str = "ACTIVE"):
    """A session.get side effect for the Workflows API."""

    def get(url, **kwargs):
        resp = MagicMock(ok=True, status_code=200)
        if "/executions/" in url:
            resp.json.return_value = {"state": state}
        else:
            resp.json.return_value = {"sourceContents": source}
        return resp

    return get


def _started_argument(session) -> dict:
    """The argument the CLI started the workflow with."""
    return json.loads(session.post.call_args.kwargs["json"]["argument"])


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
    called_args = mock_job_session.post.call_args[1]
    assert called_args["timeout"] == 300
    called_payload = called_args["json"]
    assert "argument" in called_payload
    assert json.loads(called_payload["argument"]) == expected_arg


@pytest.mark.usefixtures("mock_terraform_ingest")
def test_ingest_start_dry_run_waits_and_prints_the_report(
    runner: CliRunner, mock_job_session
) -> None:
    mock_job_session.get.side_effect = _workflow_get()
    with patch(
        "datacommons_admin.ingest.report.read_report", return_value=_REPORT
    ) as read:
        result = runner.invoke(
            admin, ["ingest", "start", "--imports", "oecd", "--mode", "dry_run"]
        )

    assert result.exit_code == 0, result.output
    assert _started_argument(mock_job_session) == {
        "imports": ["oecd"],
        "mode": "DRY_RUN",
    }
    read.assert_called_with(_REPORT_URI, "mock-proj")
    assert "Run exec-123: DRY_RUN SUCCESS" in result.output
    assert "1,200 observations (2005 to 2021), 3 nodes" in result.output


@pytest.mark.usefixtures("mock_terraform_ingest")
def test_ingest_start_ingest_mode_does_not_wait_by_default(
    runner: CliRunner, mock_job_session
) -> None:
    with patch("datacommons_admin.ingest.report.read_report") as read:
        result = runner.invoke(admin, ["ingest", "start", "--imports", "oecd"])

    assert result.exit_code == 0, result.output
    assert _started_argument(mock_job_session)["mode"] == "INGEST"
    read.assert_not_called()
    mock_job_session.get.assert_not_called()


@pytest.mark.usefixtures("mock_terraform_ingest")
def test_ingest_start_dry_run_refuses_a_workflow_without_dry_run(
    runner: CliRunner, mock_job_session
) -> None:
    """An older workflow would ignore the mode and ingest for real."""
    mock_job_session.get.side_effect = _workflow_get(source="main: ...")
    result = runner.invoke(
        admin, ["ingest", "start", "--imports", "oecd", "--mode", "dry_run"]
    )

    assert result.exit_code != 0
    assert "doesn't support dry runs yet" in result.output
    mock_job_session.post.assert_not_called()


@pytest.mark.usefixtures("mock_terraform_ingest", "mock_job_session")
def test_ingest_report_prints_json(runner: CliRunner) -> None:
    with patch("datacommons_admin.ingest.report.read_report", return_value=_REPORT):
        result = runner.invoke(admin, ["ingest", "report", "exec-123", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output[result.output.index("{") :]) == _REPORT


@pytest.mark.usefixtures("mock_terraform_ingest", "mock_job_session")
def test_ingest_report_without_a_report_yet_fails(runner: CliRunner) -> None:
    with patch("datacommons_admin.ingest.report.read_report", return_value=None):
        result = runner.invoke(admin, ["ingest", "report", "exec-123"])

    assert result.exit_code != 0
    assert f"No ingestion report at {_REPORT_URI} yet" in result.output


@pytest.mark.usefixtures("mock_terraform_ingest", "mock_job_session")
def test_ingest_report_of_a_failed_run_exits_with_an_error(runner: CliRunner) -> None:
    failed = {**_REPORT, "run": {**_REPORT["run"], "status": "FAILURE"}}
    with patch("datacommons_admin.ingest.report.read_report", return_value=failed):
        result = runner.invoke(admin, ["ingest", "report", "exec-123"])

    assert result.exit_code == 1
    assert "DRY_RUN FAILURE" in result.output
