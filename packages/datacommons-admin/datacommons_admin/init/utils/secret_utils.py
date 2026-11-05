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

import sys

import click
from google.api_core import exceptions
from google.auth import exceptions as google_auth_exceptions
from google.cloud import secretmanager

from datacommons_admin.core.utils.ui_utils import (
    _confirm,
    _log_resolved_value,
    _prompt,
)


def get_default_dc_api_key_secret_name(instance_name: str) -> str:
    """Returns the default Secret Manager secret name for the Data Commons API key."""
    prefix = f"{instance_name}-" if instance_name else ""
    return f"{prefix}dc-api-key"


def normalize_secret_id(project_id: str, secret_id_or_name: str) -> str:
    """Normalizes a short secret name or full resource ID to projects/<project_id>/secrets/<name>."""
    cleaned = secret_id_or_name.strip()
    if cleaned.startswith("projects/"):
        return cleaned
    return f"projects/{project_id}/secrets/{cleaned}"


def get_default_dc_api_key_secret_id(project_id: str, instance_name: str) -> str:
    """Returns the default full Secret Manager resource ID for the Data Commons API key."""
    return normalize_secret_id(
        project_id, get_default_dc_api_key_secret_name(instance_name)
    )


def _prompt_dc_api_key() -> str:
    """Prompts interactively for the Data Commons API key with hidden input."""
    return _prompt(
        "Data Commons API key (from apikeys.datacommons.org)",
        type=str,
        default="",
        show_default=False,
        hide_input=True,
    ).strip()


def _add_secret_version(
    secret_client: secretmanager.SecretManagerServiceClient,
    full_secret_id: str,
    api_key: str,
) -> None:
    """Adds a new secret version containing the API key payload."""
    click.secho(
        f"  Adding secret version to {full_secret_id}...",
        fg="bright_black",
    )
    secret_client.add_secret_version(
        request={
            "parent": full_secret_id,
            "payload": {"data": api_key.encode("utf-8")},
        }
    )


def _ensure_dc_api_key_secret(
    secret_client: secretmanager.SecretManagerServiceClient,
    project_id: str,
    secret_name: str,
    full_secret_id: str,
    dc_api_key: str,
) -> str:
    """Checks if the default secret exists in Secret Manager, reusing or creating it."""
    api_key = dc_api_key.strip()
    try:
        secret_client.get_secret(request={"name": full_secret_id})
        click.echo(f"  - {'Status'.ljust(12)}: Found")
        if api_key:
            _add_secret_version(secret_client, full_secret_id, api_key)
            return full_secret_id

        if _confirm("Use existing secret in Secret Manager?", default=True):
            return full_secret_id

        new_key = _prompt_dc_api_key()
        if new_key:
            _add_secret_version(secret_client, full_secret_id, new_key)
        else:
            click.secho(
                "  Keeping existing secret version unchanged.",
                fg="bright_black",
            )
        return full_secret_id

    except exceptions.NotFound:
        click.echo(f"  - {'Status'.ljust(12)}: Not found")
        if not api_key:
            api_key = _prompt_dc_api_key()

        if not api_key:
            click.secho(
                f"  [!] Warning: Data Commons API key was skipped. Create or populate '{full_secret_id}' in Secret Manager before running terraform apply.",
                fg="yellow",
                bold=True,
            )
            return full_secret_id

        click.secho(
            f"  Creating secret {full_secret_id} in Secret Manager...",
            fg="bright_black",
        )
        secret_client.create_secret(
            request={
                "parent": f"projects/{project_id}",
                "secret_id": secret_name,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        _add_secret_version(secret_client, full_secret_id, api_key)
        return full_secret_id


SECRET_MANAGER_ENABLE_DOCS_URL = (
    "https://cloud.google.com/secret-manager/docs/configuring-secret-manager"
)
SECRET_MANAGER_ACCESS_DOCS_URL = (
    "https://cloud.google.com/secret-manager/docs/access-control"
)


# Errors from Secret Manager calls that are turned into clean CLI errors.
_SECRET_MANAGER_ERRORS = (
    exceptions.GoogleAPICallError,
    exceptions.RetryError,
    google_auth_exceptions.GoogleAuthError,
)


def _secret_project(full_secret_id: str, default_project_id: str) -> str:
    """Returns the project that owns a projects/<project>/secrets/<name> resource."""
    parts = full_secret_id.split("/")
    if len(parts) >= 2 and parts[0] == "projects" and parts[1]:
        return parts[1]
    return default_project_id


def _is_service_disabled_error(error: exceptions.GoogleAPICallError) -> bool:
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
    error: Exception, project_id: str, full_secret_id: str
) -> click.ClickException:
    """Maps a Secret Manager failure to a clean, actionable CLI error."""
    if isinstance(error, (exceptions.Forbidden, exceptions.PermissionDenied)):
        if _is_service_disabled_error(error):
            return click.ClickException(
                f"The Secret Manager API is not enabled in project '{project_id}'.\n"
                "Enable it, then re-run 'datacommons admin init':\n"
                f"  gcloud services enable secretmanager.googleapis.com --project={project_id}\n"
                f"See {SECRET_MANAGER_ENABLE_DOCS_URL}"
            )
        return click.ClickException(
            f"Permission denied accessing Secret Manager secret '{full_secret_id}'.\n"
            "Your account needs the Secret Manager Admin role "
            "(roles/secretmanager.admin) on the project (or Secret Manager "
            "Secret Accessor on the secret, if you pass --dc-api-key-secret-id "
            "for a secret that already exists). Ask a project owner to grant it, "
            "then re-run 'datacommons admin init'.\n"
            f"See {SECRET_MANAGER_ACCESS_DOCS_URL}"
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
        f"Failed to access Secret Manager secret '{full_secret_id}': {error}"
    )


def _create_secret_manager_client(
    project_id: str, full_secret_id: str
) -> secretmanager.SecretManagerServiceClient:
    try:
        return secretmanager.SecretManagerServiceClient()
    except google_auth_exceptions.GoogleAuthError as e:
        raise _secret_manager_error(e, project_id, full_secret_id) from e


def _verify_existing_secret(project_id: str, full_secret_id: str) -> None:
    """Checks that a user-provided (BYO) secret exists and is accessible."""
    secret_project = _secret_project(full_secret_id, project_id)
    secret_client = _create_secret_manager_client(secret_project, full_secret_id)
    try:
        secret_client.get_secret(request={"name": full_secret_id})
    except exceptions.NotFound as e:
        raise click.ClickException(
            f"Secret '{full_secret_id}' was not found in Secret Manager.\n"
            "Create it and add the API key as a version, for example:\n"
            f"  gcloud secrets create {full_secret_id.split('/')[-1]} --project={secret_project}\n"
            f"  printf '%s' \"$DC_API_KEY\" | gcloud secrets versions add {full_secret_id.split('/')[-1]} --project={secret_project} --data-file=-\n"
            "Or omit --dc-api-key-secret-id and 'datacommons admin init' will create the secret for you."
        ) from e
    except _SECRET_MANAGER_ERRORS as e:
        raise _secret_manager_error(e, secret_project, full_secret_id) from e
    click.echo(f"  - {'Status'.ljust(12)}: Found")


def _configure_dc_api_key_secret(
    project_id: str,
    instance_name: str,
    dc_api_key_secret_id: str = "",
    dc_api_key: str = "",
) -> str:
    """Configures or provisions the Secret Manager secret for the Data Commons API key.

    Exits with an actionable error (no traceback) if Secret Manager is not
    enabled, the caller lacks permissions, or credentials are missing. Call this
    before creating any other resources so init never stops half way.
    """
    if dc_api_key_secret_id.strip():
        resolved_secret_id = normalize_secret_id(project_id, dc_api_key_secret_id)
        click.echo("Configuring Secret Manager secret for Data Commons API key:")
        _log_resolved_value("Secret ID", resolved_secret_id, is_default=False)
        _verify_existing_secret(project_id, resolved_secret_id)
        return resolved_secret_id

    secret_name = get_default_dc_api_key_secret_name(instance_name)
    full_secret_id = get_default_dc_api_key_secret_id(project_id, instance_name)

    click.echo(
        "Setting up Google Cloud Secret Manager secret for Data Commons API key:"
    )
    _log_resolved_value("Secret ID", full_secret_id, is_default=True)

    secret_client = _create_secret_manager_client(project_id, full_secret_id)

    try:
        return _ensure_dc_api_key_secret(
            secret_client=secret_client,
            project_id=project_id,
            secret_name=secret_name,
            full_secret_id=full_secret_id,
            dc_api_key=dc_api_key,
        )
    except click.Abort:
        click.echo("")
        sys.exit(1)
    except _SECRET_MANAGER_ERRORS as e:
        raise _secret_manager_error(e, project_id, full_secret_id) from e
