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


def test_configure_secret_with_explicit_secret_id_override() -> None:
    with patch(
        "datacommons_admin.init.utils.secret_utils.secretmanager.SecretManagerServiceClient"
    ) as mock_client_cls:
        result = _configure_dc_api_key_secret(
            project_id="my-proj",
            instance_name="dev",
            dc_api_key_secret_id="my-byo-secret",
        )
        assert result == "projects/my-proj/secrets/my-byo-secret"
        mock_client_cls.assert_not_called()


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
