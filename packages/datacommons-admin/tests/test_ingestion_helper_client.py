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

from unittest.mock import MagicMock, patch

import click
import pytest
import requests
from datacommons_admin.ingestion_helper_client import IngestionHelperClient


@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("google.auth.impersonated_credentials.IDTokenCredentials")
@patch("google.auth.impersonated_credentials.Credentials")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_acquire_lock_default_timeout(
    mock_auth_default: patch,
    mock_imp_creds: patch,
    mock_id_token_creds: patch,
    mock_session: patch,
) -> None:
    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")
    mock_imp_creds.return_value = MagicMock()
    mock_id_token_creds.return_value = MagicMock()

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success", "message": "Lock acquired"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    client = IngestionHelperClient(
        "https://mock-helper.a.run.app", service_account_email="sa@mock.com"
    )
    result = client.acquire_lock("schema-migration")

    assert result == {"status": "success", "message": "Lock acquired"}
    mock_session_inst.post.assert_called_once_with(
        "https://mock-helper.a.run.app/database/lock/acquire",
        json={"workflowId": "schema-migration", "timeout": 300},
        timeout=300,
    )


@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("google.auth.impersonated_credentials.IDTokenCredentials")
@patch("google.auth.impersonated_credentials.Credentials")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_acquire_lock_custom_args(
    mock_auth_default: patch,
    mock_imp_creds: patch,
    mock_id_token_creds: patch,
    mock_session: patch,
) -> None:
    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")
    mock_imp_creds.return_value = MagicMock()
    mock_id_token_creds.return_value = MagicMock()

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success", "message": "Lock acquired"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    client = IngestionHelperClient(
        "https://mock-helper.a.run.app", service_account_email="sa@mock.com"
    )
    result = client.acquire_lock("custom-migration-123", timeout=600)

    assert result == {"status": "success", "message": "Lock acquired"}
    mock_session_inst.post.assert_called_once_with(
        "https://mock-helper.a.run.app/database/lock/acquire",
        json={"workflowId": "custom-migration-123", "timeout": 600},
        timeout=300,
    )


@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("google.auth.impersonated_credentials.IDTokenCredentials")
@patch("google.auth.impersonated_credentials.Credentials")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_release_lock_success(
    mock_auth_default: patch,
    mock_imp_creds: patch,
    mock_id_token_creds: patch,
    mock_session: patch,
) -> None:
    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")
    mock_imp_creds.return_value = MagicMock()
    mock_id_token_creds.return_value = MagicMock()

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success", "message": "Lock released"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    client = IngestionHelperClient(
        "https://mock-helper.a.run.app", service_account_email="sa@mock.com"
    )
    result = client.release_lock("schema-migration")

    assert result == {"status": "success", "message": "Lock released"}
    mock_session_inst.post.assert_called_once_with(
        "https://mock-helper.a.run.app/database/lock/release",
        json={"workflowId": "schema-migration"},
        timeout=300,
    )


@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("google.auth.impersonated_credentials.IDTokenCredentials")
@patch("google.auth.impersonated_credentials.Credentials")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_release_lock_custom_workflow_id(
    mock_auth_default: patch,
    mock_imp_creds: patch,
    mock_id_token_creds: patch,
    mock_session: patch,
) -> None:
    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")
    mock_imp_creds.return_value = MagicMock()
    mock_id_token_creds.return_value = MagicMock()

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success", "message": "Lock released"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    client = IngestionHelperClient(
        "https://mock-helper.a.run.app", service_account_email="sa@mock.com"
    )
    result = client.release_lock("custom-migration-123")

    assert result == {"status": "success", "message": "Lock released"}
    mock_session_inst.post.assert_called_once_with(
        "https://mock-helper.a.run.app/database/lock/release",
        json={"workflowId": "custom-migration-123"},
        timeout=300,
    )


@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("google.auth.impersonated_credentials.IDTokenCredentials")
@patch("google.auth.impersonated_credentials.Credentials")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_lock_acquire_http_error(
    mock_auth_default: patch,
    mock_imp_creds: patch,
    mock_id_token_creds: patch,
    mock_session: patch,
) -> None:
    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")
    mock_imp_creds.return_value = MagicMock()
    mock_id_token_creds.return_value = MagicMock()

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 503
    mock_resp.json.return_value = {
        "detail": "Database lock already held by workflow-456"
    }
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    client = IngestionHelperClient(
        "https://mock-helper.a.run.app", service_account_email="sa@mock.com"
    )
    with pytest.raises(click.ClickException) as exc_info:
        client.acquire_lock("schema-migration")

    assert "Ingestion Helper returned HTTP 503" in str(exc_info.value)
    assert "Database lock already held by workflow-456" in str(exc_info.value)


@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("google.auth.impersonated_credentials.IDTokenCredentials")
@patch("google.auth.impersonated_credentials.Credentials")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_unauthorized_error(
    mock_auth_default: patch,
    mock_imp_creds: patch,
    mock_id_token_creds: patch,
    mock_session: patch,
) -> None:
    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")
    mock_imp_creds.return_value = MagicMock()
    mock_id_token_creds.return_value = MagicMock()

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 401
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    client = IngestionHelperClient(
        "https://mock-helper.a.run.app", service_account_email="sa@mock.com"
    )
    with pytest.raises(click.ClickException) as exc_info:
        client.acquire_lock("schema-migration")

    assert "HTTP 401 Unauthorized when calling Ingestion Helper" in str(exc_info.value)


@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("google.auth.impersonated_credentials.IDTokenCredentials")
@patch("google.auth.impersonated_credentials.Credentials")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_network_request_exception(
    mock_auth_default: patch,
    mock_imp_creds: patch,
    mock_id_token_creds: patch,
    mock_session: patch,
) -> None:
    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")
    mock_imp_creds.return_value = MagicMock()
    mock_id_token_creds.return_value = MagicMock()

    mock_session_inst = MagicMock()
    mock_session_inst.post.side_effect = requests.exceptions.ConnectionError(
        "Connection refused"
    )
    mock_session.return_value = mock_session_inst

    client = IngestionHelperClient(
        "https://mock-helper.a.run.app", service_account_email="sa@mock.com"
    )
    with pytest.raises(click.ClickException) as exc_info:
        client.release_lock("schema-migration")

    assert "Network or authentication error" in str(exc_info.value)


@patch("datacommons_admin.ingestion_helper_client.AuthorizedSession")
@patch("datacommons_admin.ingestion_helper_client.id_token.fetch_id_token")
@patch("datacommons_admin.ingestion_helper_client.google.auth.default")
def test_id_token_fetch_when_no_service_account(
    mock_auth_default: patch,
    mock_fetch_id_token: patch,
    mock_session: patch,
) -> None:
    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, "test-project")
    mock_fetch_id_token.return_value = "mock-id-token"

    mock_session_inst = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"status": "success"}
    mock_session_inst.post.return_value = mock_resp
    mock_session.return_value = mock_session_inst

    client = IngestionHelperClient("https://mock-helper.a.run.app")
    result = client.initialize_database()

    assert result == {"status": "success"}
    mock_fetch_id_token.assert_called_once()


def test_localhost_bypass_auth() -> None:
    client = IngestionHelperClient("http://localhost:8080")
    assert isinstance(client.session, requests.Session)
