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

"""Sets up the Data Commons API key secret in Secret Manager for `admin init`.

Terraform only references the secret by name (auth_dc_api_key_secret_id); the
key itself never goes into terraform.tfvars or Terraform state.
"""

import re

import click
from google.api_core import exceptions
from google.auth import exceptions as google_auth_exceptions
from google.cloud import secretmanager

from datacommons_admin.core.utils.ui_utils import (
    _confirm,
    _log_resolved_value,
    _prompt,
)

_SECRET_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_API_KEY_URL = "https://apikeys.datacommons.org"
_ENABLE_API_DOCS_URL = (
    "https://cloud.google.com/secret-manager/docs/configuring-secret-manager"
)
_ACCESS_CONTROL_DOCS_URL = "https://cloud.google.com/secret-manager/docs/access-control"

# Failures from the Secret Manager client that are turned into clean CLI errors.
_SECRET_MANAGER_ERRORS = (
    exceptions.GoogleAPICallError,
    exceptions.RetryError,
    google_auth_exceptions.GoogleAuthError,
)


# -----------------------------------------------------------------------------
# Names
# -----------------------------------------------------------------------------


def default_dc_api_key_secret_name(instance_name: str) -> str:
    """Returns "<instance_name>-dc-api-key" (or "dc-api-key" with no instance name)."""
    prefix = f"{instance_name}-" if instance_name else ""
    return f"{prefix}dc-api-key"


def secret_path(project_id: str, secret_name: str) -> str:
    """Returns the full resource name: projects/<project_id>/secrets/<secret_name>."""
    return f"projects/{project_id}/secrets/{secret_name}"


def validate_secret_name(secret_name: str) -> str:
    """Returns the stripped secret name, or raises if it isn't a plain name.

    The secret must live in the instance's project, so full resource paths
    (projects/<project>/secrets/<name>) are rejected.
    """
    cleaned = secret_name.strip()
    if not _SECRET_NAME_RE.match(cleaned):
        raise click.ClickException(
            f"Invalid --dc-api-key-secret-id '{cleaned}'. Pass the name of a "
            "Secret Manager secret in --project-id (letters, digits, '-' and "
            "'_'), e.g. 'my-dc-api-key', not a full resource path."
        )
    return cleaned


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


def _configure_dc_api_key_secret(
    project_id: str,
    instance_name: str,
    dc_api_key_secret_id: str = "",
    dc_api_key: str = "",
) -> str:
    """Creates, reuses or verifies the Data Commons API key secret.

    - With dc_api_key_secret_id: verifies that secret exists in project_id.
    - Otherwise: reuses or creates "<instance_name>-dc-api-key", using
      dc_api_key (from DC_API_KEY or the deprecated flag) or a hidden prompt.

    Returns the secret name to write to terraform.tfvars. Raises a ClickException
    with an actionable message (no traceback) if Secret Manager is disabled, the
    caller lacks permissions, or credentials are missing. Call this before
    creating anything else so init never stops half way.
    """
    use_existing = bool(dc_api_key_secret_id.strip())
    if use_existing:
        secret_name = validate_secret_name(dc_api_key_secret_id)
        click.echo("Configuring Secret Manager secret for Data Commons API key:")
    else:
        secret_name = default_dc_api_key_secret_name(instance_name)
        click.echo(
            "Setting up Google Cloud Secret Manager secret for Data Commons API key:"
        )
    path = secret_path(project_id, secret_name)
    _log_resolved_value("Secret ID", path, is_default=not use_existing)

    try:
        client = secretmanager.SecretManagerServiceClient()
        if use_existing:
            _verify_existing_secret(client, project_id, secret_name)
        else:
            _ensure_default_secret(client, project_id, secret_name, dc_api_key.strip())
    except _SECRET_MANAGER_ERRORS as e:
        raise _secret_manager_error(e, project_id, path) from e
    return secret_name


# -----------------------------------------------------------------------------
# Secret Manager operations
# -----------------------------------------------------------------------------


def _verify_existing_secret(
    client: secretmanager.SecretManagerServiceClient,
    project_id: str,
    secret_name: str,
) -> None:
    """Checks that a user-provided (--dc-api-key-secret-id) secret exists."""
    path = secret_path(project_id, secret_name)
    if not _secret_exists(client, path):
        raise click.ClickException(
            f"Secret '{path}' was not found in Secret Manager.\n"
            "Create it and add the API key as a version, for example:\n"
            f"  gcloud secrets create {secret_name} --project={project_id}\n"
            f"  printf '%s' \"$DC_API_KEY\" | gcloud secrets versions add {secret_name} --project={project_id} --data-file=-\n"
            "Or omit --dc-api-key-secret-id and 'datacommons admin init' will create the secret for you."
        )
    click.echo(f"  - {'Status'.ljust(12)}: Found")


def _ensure_default_secret(
    client: secretmanager.SecretManagerServiceClient,
    project_id: str,
    secret_name: str,
    api_key: str,
) -> None:
    """Reuses the default secret if it exists, otherwise creates it."""
    path = secret_path(project_id, secret_name)

    if _secret_exists(client, path):
        click.echo(f"  - {'Status'.ljust(12)}: Found")
        if not api_key:
            if _confirm("Use existing secret in Secret Manager?", default=True):
                return
            api_key = _prompt_dc_api_key()
        if api_key:
            _add_version_if_changed(client, path, api_key)
        else:
            click.secho("  Keeping existing secret version.", fg="bright_black")
        return

    click.echo(f"  - {'Status'.ljust(12)}: Not found")
    api_key = api_key or _prompt_dc_api_key()
    if not api_key:
        # Terraform requires the secret to exist, so don't scaffold without it.
        raise click.ClickException(
            f"A Data Commons API key is required to create '{path}'. Get one at "
            f"{_API_KEY_URL}, then re-run with the DC_API_KEY environment variable "
            "set (or enter it at the prompt), or pass --dc-api-key-secret-id to use "
            "an existing secret."
        )
    click.secho(f"  Creating secret {path} in Secret Manager...", fg="bright_black")
    client.create_secret(
        request={
            "parent": f"projects/{project_id}",
            "secret_id": secret_name,
            "secret": {"replication": {"automatic": {}}},
        }
    )
    _add_secret_version(client, path, api_key)


def _secret_exists(client: secretmanager.SecretManagerServiceClient, path: str) -> bool:
    try:
        client.get_secret(request={"name": path})
        return True
    except exceptions.NotFound:
        return False


def _add_version_if_changed(
    client: secretmanager.SecretManagerServiceClient, path: str, api_key: str
) -> None:
    """Adds a version unless the latest version already holds this key.

    If the latest version can't be read (none enabled, or no accessor
    permission), a new version is added.
    """
    try:
        latest = client.access_secret_version(
            request={"name": f"{path}/versions/latest"}
        )
        if latest.payload.data.decode("utf-8") == api_key:
            click.secho(
                "  Secret already holds this API key; no new version added.",
                fg="bright_black",
            )
            return
    except (
        exceptions.NotFound,
        exceptions.FailedPrecondition,
        exceptions.PermissionDenied,
    ):
        pass
    _add_secret_version(client, path, api_key)


def _add_secret_version(
    client: secretmanager.SecretManagerServiceClient, path: str, api_key: str
) -> None:
    click.secho(f"  Adding secret version to {path}...", fg="bright_black")
    client.add_secret_version(
        request={"parent": path, "payload": {"data": api_key.encode("utf-8")}}
    )


def _prompt_dc_api_key() -> str:
    """Prompts for the Data Commons API key with hidden input."""
    return _prompt(
        f"Data Commons API key (from {_API_KEY_URL.removeprefix('https://')})",
        type=str,
        default="",
        show_default=False,
        hide_input=True,
    ).strip()


# -----------------------------------------------------------------------------
# Error handling
# -----------------------------------------------------------------------------


def _is_service_disabled_error(error: Exception) -> bool:
    """Returns True if the error says the Secret Manager API is not enabled."""
    if getattr(error, "reason", None) == "SERVICE_DISABLED":
        return True
    message = str(error)
    return (
        "SERVICE_DISABLED" in message
        or "has not been used in project" in message
        or "it is disabled" in message
    )


def _secret_manager_error(
    error: Exception, project_id: str, path: str
) -> click.ClickException:
    """Maps a Secret Manager failure to a clean, actionable CLI error."""
    if isinstance(error, (exceptions.Forbidden, exceptions.PermissionDenied)):
        if _is_service_disabled_error(error):
            return click.ClickException(
                f"The Secret Manager API is not enabled in project '{project_id}'.\n"
                "Enable it, then re-run 'datacommons admin init':\n"
                f"  gcloud services enable secretmanager.googleapis.com --project={project_id}\n"
                f"See {_ENABLE_API_DOCS_URL}"
            )
        return click.ClickException(
            f"Permission denied accessing Secret Manager secret '{path}'.\n"
            f"Ask a project owner to grant you, on project '{project_id}':\n"
            "  - Secret Manager Admin (roles/secretmanager.admin) to let init "
            "create or update the secret, or\n"
            "  - Secret Manager Viewer (roles/secretmanager.viewer) to use an "
            "existing secret with --dc-api-key-secret-id.\n"
            "Then re-run 'datacommons admin init'.\n"
            f"See {_ACCESS_CONTROL_DOCS_URL}"
        )
    if isinstance(
        error,
        (
            exceptions.Unauthenticated,
            exceptions.Unauthorized,
            google_auth_exceptions.GoogleAuthError,
        ),
    ):
        return click.ClickException(
            "Could not authenticate to Google Cloud. Run "
            "'gcloud auth application-default login', then re-run "
            "'datacommons admin init'."
        )
    return click.ClickException(
        f"Failed to access Secret Manager secret '{path}': {error}"
    )
