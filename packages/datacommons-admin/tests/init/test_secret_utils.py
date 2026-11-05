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
from datacommons_admin.init.utils.secret_utils import (
    _configure_dc_api_key_secret,
    get_default_dc_api_key_secret_id,
    get_default_dc_api_key_secret_name,
    normalize_secret_id,
)
from google.api_core import exceptions
from google.rpc import error_details_pb2


def test_secret_name_and_normalization_helpers() -> None:
    assert get_default_dc_api_key_secret_name("prod") == "prod-dc-api-key"
    assert get_default_dc_api_key_secret_name("") == "dc-api-key"
    assert (
        get_default_dc_api_key_secret_id("my-proj", "prod")
        == "projects/my-proj/secrets/prod-dc-api-key"
    )
    assert (
        normalize_secret_id("my-proj", "custom-secret")
        == "projects/my-proj/secrets/custom-secret"
    )
    assert (
        normalize_secret_id("my-proj", "projects/other-proj/secrets/shared-secret")
        == "projects/other-proj/secrets/shared-secret"
    )


def test_configure_secret_with_explicit_secret_id_override_verifies_it_exists() -> None:
    with patch(
        "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        result = _configure_dc_api_key_secret(
            project_id="my-proj",
            instance_name="dev",
            dc_api_key_secret_id="my-byo-secret",
        )
        assert result == "projects/my-proj/secrets/my-byo-secret"
        mock_client.get_secret.assert_called_once_with(
            request={"name": "projects/my-proj/secrets/my-byo-secret"}
        )
        mock_client.create_secret.assert_not_called()
        mock_client.add_secret_version.assert_not_called()


def test_configure_secret_with_missing_byo_secret_explains_how_to_create_it() -> None:
    with patch(
        "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = exceptions.NotFound("not found")
        mock_client_cls.return_value = mock_client

        with pytest.raises(click.ClickException) as exc_info:
            _configure_dc_api_key_secret(
                project_id="my-proj",
                instance_name="dev",
                dc_api_key_secret_id="projects/other-proj/secrets/shared",
            )
        message = str(exc_info.value)
        assert "projects/other-proj/secrets/shared" in message
        assert "gcloud secrets create shared --project=other-proj" in message
        mock_client.create_secret.assert_not_called()


def test_configure_secret_creates_new_secret_when_not_found() -> None:
    with patch(
        "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = exceptions.NotFound("Secret not found")
        mock_created = MagicMock()
        mock_created.name = "projects/my-proj/secrets/dev-dc-api-key"
        mock_client.create_secret.return_value = mock_created
        mock_client_cls.return_value = mock_client

        result = _configure_dc_api_key_secret(
            project_id="my-proj",
            instance_name="dev",
            dc_api_key="my-secret-api-key",
        )

        assert result == "projects/my-proj/secrets/dev-dc-api-key"
        mock_client.create_secret.assert_called_once_with(
            request={
                "parent": "projects/my-proj",
                "secret_id": "dev-dc-api-key",
                "secret": {"replication": {"automatic": {}}},
            }
        )
        mock_client.add_secret_version.assert_called_once_with(
            request={
                "parent": "projects/my-proj/secrets/dev-dc-api-key",
                "payload": {"data": b"my-secret-api-key"},
            }
        )


def test_configure_secret_prompts_with_hidden_input_when_missing() -> None:
    with (
        patch(
            "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient"
        ) as mock_client_cls,
        patch(
            "datacommons_admin.init.utils.secret_utils._prompt",
            return_value="prompted-secret-key",
        ) as mock_prompt,
    ):
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = exceptions.NotFound("Secret not found")
        mock_created = MagicMock()
        mock_created.name = "projects/my-proj/secrets/dev-dc-api-key"
        mock_client.create_secret.return_value = mock_created
        mock_client_cls.return_value = mock_client

        result = _configure_dc_api_key_secret(
            project_id="my-proj",
            instance_name="dev",
        )

        assert result == "projects/my-proj/secrets/dev-dc-api-key"
        mock_prompt.assert_called_once()
        assert mock_prompt.call_args.kwargs.get("hide_input") is True
        mock_client.add_secret_version.assert_called_once_with(
            request={
                "parent": "projects/my-proj/secrets/dev-dc-api-key",
                "payload": {"data": b"prompted-secret-key"},
            }
        )


def test_configure_secret_reuses_existing_secret_on_confirm() -> None:
    with (
        patch(
            "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient"
        ) as mock_client_cls,
        patch(
            "datacommons_admin.init.utils.secret_utils._confirm",
            return_value=True,
        ) as mock_confirm,
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        result = _configure_dc_api_key_secret(
            project_id="my-proj",
            instance_name="dev",
        )

        assert result == "projects/my-proj/secrets/dev-dc-api-key"
        mock_confirm.assert_called_once()
        mock_client.create_secret.assert_not_called()
        mock_client.add_secret_version.assert_not_called()


def test_configure_secret_service_disabled_gives_actionable_error() -> None:
    with patch(
        "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = exceptions.PermissionDenied(
            "403 Secret Manager API has not been used in project my-proj (SERVICE_DISABLED)"
        )
        mock_client_cls.return_value = mock_client

        with pytest.raises(click.ClickException) as exc_info:
            _configure_dc_api_key_secret(
                project_id="my-proj",
                instance_name="dev",
                dc_api_key="test-key",
            )
        assert (
            "gcloud services enable secretmanager.googleapis.com --project=my-proj"
            in str(exc_info.value)
        )


def test_configure_secret_service_disabled_detected_from_error_reason() -> None:
    with patch(
        "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = exceptions.PermissionDenied(
            "403 forbidden",
            error_info=error_details_pb2.ErrorInfo(reason="SERVICE_DISABLED"),
        )
        mock_client_cls.return_value = mock_client
        with pytest.raises(click.ClickException) as exc_info:
            _configure_dc_api_key_secret(project_id="my-proj", instance_name="dev")
        message = str(exc_info.value)
        assert (
            "gcloud services enable secretmanager.googleapis.com --project=my-proj"
            in message
        )
        assert (
            "https://cloud.google.com/secret-manager/docs/configuring-secret-manager"
            in message
        )


def test_configure_secret_service_disabled_for_byo_secret_uses_secret_project() -> None:
    with patch(
        "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = exceptions.PermissionDenied(
            "403 Secret Manager API has not been used in project other-proj before or it is disabled."
        )
        mock_client_cls.return_value = mock_client
        with pytest.raises(click.ClickException) as exc_info:
            _configure_dc_api_key_secret(
                project_id="my-proj",
                instance_name="dev",
                dc_api_key_secret_id="projects/other-proj/secrets/shared",
            )
        assert "--project=other-proj" in str(exc_info.value)


def test_configure_secret_permission_denied_names_role_and_docs() -> None:
    with patch(
        "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = exceptions.PermissionDenied(
            "403 Permission 'secretmanager.secrets.get' denied for resource"
        )
        mock_client_cls.return_value = mock_client
        with pytest.raises(click.ClickException) as exc_info:
            _configure_dc_api_key_secret(project_id="my-proj", instance_name="dev")
        message = str(exc_info.value)
        assert "roles/secretmanager.admin" in message
        assert "https://cloud.google.com/secret-manager/docs/access-control" in message
        assert "gcloud services enable" not in message


def test_configure_secret_permission_denied_on_create_is_clean() -> None:
    with patch(
        "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = exceptions.NotFound("not found")
        mock_client.create_secret.side_effect = exceptions.PermissionDenied(
            "403 Permission 'secretmanager.secrets.create' denied"
        )
        mock_client_cls.return_value = mock_client
        with pytest.raises(click.ClickException) as exc_info:
            _configure_dc_api_key_secret(
                project_id="my-proj", instance_name="dev", dc_api_key="test-key"
            )
        assert "roles/secretmanager.admin" in str(exc_info.value)


def test_configure_secret_missing_credentials_is_clean() -> None:
    from google.auth import exceptions as google_auth_exceptions

    with patch(
        "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient",
        side_effect=google_auth_exceptions.DefaultCredentialsError("no ADC"),
    ):
        with pytest.raises(click.ClickException) as exc_info:
            _configure_dc_api_key_secret(project_id="my-proj", instance_name="dev")
        assert "gcloud auth application-default login" in str(exc_info.value)
