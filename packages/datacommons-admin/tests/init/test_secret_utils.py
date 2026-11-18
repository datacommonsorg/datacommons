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
    default_dc_api_key_secret_name,
    secret_path,
    validate_secret_name,
)
from google.api_core import exceptions
from google.auth import exceptions as google_auth_exceptions
from google.rpc import error_details_pb2

_MODULE = "datacommons_admin.init.utils.secret_utils"
_DEFAULT_PATH = "projects/my-proj/secrets/dev-dc-api-key"


@pytest.fixture
def client() -> MagicMock:
    """A mocked SecretManagerServiceClient; by default the secret exists."""
    with patch(f"{_MODULE}.secretmanager.SecretManagerServiceClient") as cls:
        mock = MagicMock()
        cls.return_value = mock
        yield mock


@pytest.fixture
def prompt() -> MagicMock:
    with patch(f"{_MODULE}._prompt", return_value="") as mock:
        yield mock


@pytest.fixture
def confirm() -> MagicMock:
    with patch(f"{_MODULE}._confirm", return_value=True) as mock:
        yield mock


def _configure(**kwargs) -> str:
    return _configure_dc_api_key_secret(
        project_id="my-proj", instance_name="dev", **kwargs
    )


def _latest_version(payload: str) -> MagicMock:
    version = MagicMock()
    version.payload.data = payload.encode("utf-8")
    return version


# -----------------------------------------------------------------------------
# Names
# -----------------------------------------------------------------------------


def test_name_helpers() -> None:
    assert default_dc_api_key_secret_name("prod") == "prod-dc-api-key"
    assert default_dc_api_key_secret_name("") == "dc-api-key"
    assert secret_path("my-proj", "s") == "projects/my-proj/secrets/s"
    assert validate_secret_name("  custom_secret-1 ") == "custom_secret-1"


@pytest.mark.parametrize(
    "bad", ["projects/other-proj/secrets/shared", "a/b", "has space", "dc.api.key"]
)
def test_validate_secret_name_rejects_paths_and_bad_chars(bad: str) -> None:
    with pytest.raises(click.ClickException, match="not a full resource path"):
        validate_secret_name(bad)


# -----------------------------------------------------------------------------
# --dc-api-key-secret-id (existing secret)
# -----------------------------------------------------------------------------


def test_existing_secret_is_verified_and_returned_by_name(client: MagicMock) -> None:
    assert _configure(dc_api_key_secret_id="my-byo-secret") == "my-byo-secret"
    client.get_secret.assert_called_once_with(
        request={"name": "projects/my-proj/secrets/my-byo-secret"}
    )
    client.create_secret.assert_not_called()
    client.add_secret_version.assert_not_called()


def test_existing_secret_full_path_rejected_before_any_api_call() -> None:
    with patch(f"{_MODULE}.secretmanager.SecretManagerServiceClient") as cls:
        with pytest.raises(click.ClickException):
            _configure(dc_api_key_secret_id="projects/other-proj/secrets/shared")
        cls.assert_not_called()


def test_missing_existing_secret_explains_how_to_create_it(client: MagicMock) -> None:
    client.get_secret.side_effect = exceptions.NotFound("not found")
    with pytest.raises(click.ClickException) as exc_info:
        _configure(dc_api_key_secret_id="shared")
    message = str(exc_info.value)
    assert "projects/my-proj/secrets/shared" in message
    assert "gcloud secrets create shared --project=my-proj" in message
    client.create_secret.assert_not_called()


# -----------------------------------------------------------------------------
# Default secret: not found -> create
# -----------------------------------------------------------------------------


def test_creates_secret_with_key_from_env(client: MagicMock, prompt) -> None:
    client.get_secret.side_effect = exceptions.NotFound("not found")

    assert _configure(dc_api_key="my-key") == "dev-dc-api-key"

    prompt.assert_not_called()
    client.create_secret.assert_called_once_with(
        request={
            "parent": "projects/my-proj",
            "secret_id": "dev-dc-api-key",
            "secret": {"replication": {"automatic": {}}},
        }
    )
    client.add_secret_version.assert_called_once_with(
        request={"parent": _DEFAULT_PATH, "payload": {"data": b"my-key"}}
    )


def test_creates_secret_with_hidden_prompt(client: MagicMock, prompt) -> None:
    client.get_secret.side_effect = exceptions.NotFound("not found")
    prompt.return_value = " prompted-key "

    assert _configure() == "dev-dc-api-key"

    assert prompt.call_args.kwargs["hide_input"] is True
    client.add_secret_version.assert_called_once_with(
        request={"parent": _DEFAULT_PATH, "payload": {"data": b"prompted-key"}}
    )


def test_missing_key_for_new_secret_fails_instead_of_scaffolding(
    client: MagicMock, prompt
) -> None:
    client.get_secret.side_effect = exceptions.NotFound("not found")

    with pytest.raises(click.ClickException, match="API key is required"):
        _configure()

    client.create_secret.assert_not_called()


# -----------------------------------------------------------------------------
# Default secret: found -> reuse / update
# -----------------------------------------------------------------------------


def test_reuses_existing_secret_on_confirm(client: MagicMock, confirm, prompt) -> None:
    assert _configure() == "dev-dc-api-key"

    confirm.assert_called_once()
    prompt.assert_not_called()
    client.add_secret_version.assert_not_called()


def test_declining_reuse_and_entering_new_key_adds_version(
    client: MagicMock, confirm, prompt
) -> None:
    confirm.return_value = False
    prompt.return_value = "new-key"
    client.access_secret_version.return_value = _latest_version("old-key")

    _configure()

    client.add_secret_version.assert_called_once_with(
        request={"parent": _DEFAULT_PATH, "payload": {"data": b"new-key"}}
    )


def test_declining_reuse_and_skipping_keeps_existing_version(
    client: MagicMock, confirm, prompt
) -> None:
    confirm.return_value = False

    assert _configure() == "dev-dc-api-key"

    client.add_secret_version.assert_not_called()


def test_same_key_from_env_does_not_add_version(client: MagicMock, confirm) -> None:
    client.access_secret_version.return_value = _latest_version("my-key")

    _configure(dc_api_key="my-key")

    confirm.assert_not_called()
    client.access_secret_version.assert_called_once_with(
        request={"name": f"{_DEFAULT_PATH}/versions/latest"}
    )
    client.add_secret_version.assert_not_called()


def test_changed_key_from_env_adds_version(client: MagicMock) -> None:
    client.access_secret_version.return_value = _latest_version("old-key")

    _configure(dc_api_key="new-key")

    client.add_secret_version.assert_called_once_with(
        request={"parent": _DEFAULT_PATH, "payload": {"data": b"new-key"}}
    )


@pytest.mark.parametrize(
    "error",
    [
        exceptions.NotFound("no versions"),
        exceptions.FailedPrecondition("latest version disabled"),
        exceptions.PermissionDenied("no accessor permission"),
    ],
)
def test_unreadable_latest_version_adds_version(
    client: MagicMock, error: Exception
) -> None:
    client.access_secret_version.side_effect = error

    _configure(dc_api_key="my-key")

    client.add_secret_version.assert_called_once()


# -----------------------------------------------------------------------------
# Clean errors
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        exceptions.PermissionDenied(
            "403 Secret Manager API has not been used in project my-proj before or it is disabled."
        ),
        exceptions.PermissionDenied(
            "403 forbidden",
            error_info=error_details_pb2.ErrorInfo(reason="SERVICE_DISABLED"),
        ),
    ],
    ids=["from_message", "from_error_info_reason"],
)
def test_service_disabled_gives_enable_command_and_docs(
    client: MagicMock, error: Exception
) -> None:
    client.get_secret.side_effect = error
    with pytest.raises(click.ClickException) as exc_info:
        _configure()
    message = str(exc_info.value)
    assert (
        "gcloud services enable secretmanager.googleapis.com --project=my-proj"
        in message
    )
    assert "configuring-secret-manager" in message


@pytest.mark.parametrize("failing_call", ["get_secret", "create_secret"])
def test_permission_denied_names_roles_and_docs(
    client: MagicMock, failing_call: str
) -> None:
    if failing_call == "create_secret":
        client.get_secret.side_effect = exceptions.NotFound("not found")
    getattr(client, failing_call).side_effect = exceptions.PermissionDenied(
        f"403 Permission 'secretmanager.secrets.{failing_call.split('_')[0]}' denied"
    )
    with pytest.raises(click.ClickException) as exc_info:
        _configure(dc_api_key="my-key")
    message = str(exc_info.value)
    assert "roles/secretmanager.admin" in message
    assert "roles/secretmanager.viewer" in message
    assert "access-control" in message
    assert "gcloud services enable" not in message


def test_missing_credentials_suggests_adc_login() -> None:
    with patch(
        f"{_MODULE}.secretmanager.SecretManagerServiceClient",
        side_effect=google_auth_exceptions.DefaultCredentialsError("no ADC"),
    ):
        with pytest.raises(
            click.ClickException, match="gcloud auth application-default login"
        ):
            _configure()


def test_abort_at_prompt_propagates(client: MagicMock) -> None:
    client.get_secret.side_effect = exceptions.NotFound("not found")
    with patch(f"{_MODULE}._prompt", side_effect=click.Abort()):
        with pytest.raises(click.Abort):
            _configure()
