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
        created_secret = secret_client.create_secret(
            request={
                "parent": f"projects/{project_id}",
                "secret_id": secret_name,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        _add_secret_version(secret_client, created_secret.name, api_key)
        return full_secret_id


def _configure_dc_api_key_secret(
    project_id: str,
    instance_name: str,
    dc_api_key_secret_id: str = "",
    dc_api_key: str = "",
) -> str:
    """Configures or provisions the Secret Manager secret for the Data Commons API key."""
    if dc_api_key_secret_id.strip():
        resolved_secret_id = normalize_secret_id(project_id, dc_api_key_secret_id)
        click.echo("Configuring Secret Manager secret for Data Commons API key:")
        _log_resolved_value("Secret ID", resolved_secret_id, is_default=False)
        return resolved_secret_id

    secret_name = get_default_dc_api_key_secret_name(instance_name)
    full_secret_id = get_default_dc_api_key_secret_id(project_id, instance_name)

    click.echo(
        "Setting up Google Cloud Secret Manager secret for Data Commons API key:"
    )
    _log_resolved_value("Secret ID", full_secret_id, is_default=True)

    try:
        secret_client = secretmanager.SecretManagerServiceClient()
    except Exception as e:
        raise click.ClickException(
            f"Failed to initialize Google Cloud Secret Manager client for project '{project_id}': {e}. "
            "Ensure you are authenticated via 'gcloud auth application-default login'."
        ) from e

    try:
        return _ensure_dc_api_key_secret(
            secret_client=secret_client,
            project_id=project_id,
            secret_name=secret_name,
            full_secret_id=full_secret_id,
            dc_api_key=dc_api_key,
        )
    except (exceptions.Unauthenticated, exceptions.Unauthorized) as e:
        raise click.ClickException(
            f"Authentication failed: {e}\n"
            "Please ensure you are authenticated. Run 'gcloud auth application-default login' and try again."
        ) from e
    except (exceptions.Forbidden, exceptions.PermissionDenied) as e:
        err_str = str(e)
        if "SERVICE_DISABLED" in err_str or "secretmanager.googleapis.com" in err_str:
            raise click.ClickException(
                f"Secret Manager API is not enabled in project '{project_id}'.\n"
                "Enable it by running:\n"
                f"  gcloud services enable secretmanager.googleapis.com --project={project_id}\n"
                "Then re-run 'datacommons admin init', or pass --dc-api-key-secret-id to configure the secret ID without calling Secret Manager."
            ) from e
        raise click.ClickException(
            f"Permission denied accessing Secret Manager in project '{project_id}': {e}\n"
            f"Please ensure your account has 'Secret Manager Admin' (roles/secretmanager.admin) or 'Project Editor' permissions in project '{project_id}'."
        ) from e
    except click.Abort:
        click.echo("")
        sys.exit(1)
    except Exception as e:
        click.secho(
            f"  Error: Failed to access or create secret {full_secret_id}.",
            fg="red",
            bold=True,
        )
        click.secho(f"  {e}", fg="red")
        raise click.ClickException("Setup cancelled.") from e
