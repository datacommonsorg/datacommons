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

from click.testing import CliRunner
from datacommons_admin.admin_cli import admin


@patch("datacommons_admin.core.utils.tf_utils.shutil.which")
@patch("datacommons_admin.core.utils.tf_utils.subprocess.run")
@patch("datacommons_admin.core.clients.ingestion_job_client.AuthorizedSession")
@patch("datacommons_admin.core.clients.ingestion_job_client.google.auth.default")
def test_ingest_start_success(
    mock_auth_default,
    mock_session,
    mock_run,
    mock_which,
    runner: CliRunner,
    mock_tf_output_ingest: str,
) -> None:
    mock_which.return_value = "terraform"
    mock_proc = MagicMock()
    mock_proc.stdout = mock_tf_output_ingest
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()

    # Mock GET for get_config
    mock_get_resp = MagicMock()
    mock_get_resp.ok = True
    mock_get_resp.json.return_value = {
        "template": {
            "template": {
                "containers": [
                    {
                        "env": [
                            {"name": "TEMP_LOCATION", "value": "gs://mock-bucket/temp"},
                            {
                                "name": "GCP_SPANNER_INSTANCE_ID",
                                "value": "mock-instance",
                            },
                            {"name": "GCP_SPANNER_DATABASE_NAME", "value": "mock-db"},
                            {"name": "REGION", "value": "us-central1"},
                        ]
                    }
                ]
            }
        }
    }
    mock_session_inst.get.return_value = mock_get_resp

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "name": "projects/mock-proj/locations/us-central1/workflows/mock-workflow/executions/exec-123"
    }
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

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


@patch("datacommons_admin.core.utils.tf_utils.shutil.which")
@patch("datacommons_admin.core.utils.tf_utils.subprocess.run")
@patch("datacommons_admin.core.clients.ingestion_job_client.AuthorizedSession")
@patch("datacommons_admin.core.clients.ingestion_job_client.google.auth.default")
def test_ingest_show_config_success(
    mock_auth_default,
    mock_session,
    mock_run,
    mock_which,
    runner: CliRunner,
    mock_tf_output_ingest: str,
) -> None:
    mock_which.return_value = "terraform"
    mock_proc = MagicMock()
    mock_proc.stdout = mock_tf_output_ingest
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "template": {
            "template": {
                "containers": [
                    {
                        "env": [
                            {"name": "GCS_BUCKET", "value": "my-test-bucket"},
                            {"name": "API_KEY", "valueSource": "secret-api-key"},
                        ]
                    }
                ]
            }
        }
    }
    mock_session_inst.get.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    result = runner.invoke(admin, ["ingest", "show-config"])
    assert result.exit_code == 0
    assert "GCS_BUCKET: my-test-bucket" in result.output
    assert "API_KEY: [SECRET: secret-api-key]" in result.output


@patch("datacommons_admin.core.utils.tf_utils.shutil.which")
@patch("datacommons_admin.core.utils.tf_utils.subprocess.run")
@patch("datacommons_admin.core.clients.ingestion_job_client.AuthorizedSession")
@patch("datacommons_admin.core.clients.ingestion_job_client.google.auth.default")
def test_ingest_start_with_imports_success(
    mock_auth_default,
    mock_session,
    mock_run,
    mock_which,
    runner: CliRunner,
    mock_tf_output_ingest: str,
) -> None:
    mock_which.return_value = "terraform"
    mock_proc = MagicMock()
    mock_proc.stdout = mock_tf_output_ingest
    mock_run.return_value = mock_proc

    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")

    mock_session_inst = MagicMock()

    # Mock GET for get_config
    mock_get_resp = MagicMock()
    mock_get_resp.ok = True
    mock_get_resp.json.return_value = {
        "template": {
            "template": {
                "containers": [
                    {
                        "env": [
                            {"name": "TEMP_LOCATION", "value": "gs://mock-bucket/temp"},
                            {
                                "name": "GCP_SPANNER_INSTANCE_ID",
                                "value": "mock-instance",
                            },
                            {"name": "GCP_SPANNER_DATABASE_NAME", "value": "mock-db"},
                            {"name": "REGION", "value": "us-central1"},
                        ]
                    }
                ]
            }
        }
    }
    mock_session_inst.get.return_value = mock_get_resp

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "name": "projects/mock-proj/locations/us-central1/workflows/mock-workflow/executions/exec-123"
    }
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    result = runner.invoke(admin, ["ingest", "start", "--imports", "oecd,doubleup"])
    assert result.exit_code == 0
    assert "Successfully started ingestion workflow!" in result.output

    expected_arg = {
        "tempLocation": "gs://mock-bucket/temp",
        "spannerInstanceId": "mock-instance",
        "spannerDatabaseId": "mock-db",
        "region": "us-central1",
        "imports": ["oecd", "doubleup"],
    }

    # Verify the API was called with the correct argument
    called_args = mock_session_inst.post.call_args[1]
    assert called_args["timeout"] == 300
    called_payload = called_args["json"]
    assert "argument" in called_payload
    assert json.loads(called_payload["argument"]) == expected_arg
