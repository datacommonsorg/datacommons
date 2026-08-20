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
from google.cloud import storage

from datacommons_admin.shared_utils.ui_utils import (
    _confirm,
    _log_resolved_value,
)


DEFAULT_BUCKET_LOCATION = "US"


def _get_default_bucket_name(instance_name: str, project_id: str) -> str:
    """Returns the default Google Cloud Storage bucket name for Terraform state."""
    return f"tf-state-{instance_name}-{project_id}"


def _get_default_state_prefix(instance_name: str) -> str:
    """Returns the default Google Cloud Storage object prefix for Terraform state."""
    return f"terraform/state/{instance_name}"


def _create_and_configure_bucket(
    storage_client,
    bucket_name: str,
    project_id: str,
    location: str = DEFAULT_BUCKET_LOCATION,
) -> bool:
    """Prompts and creates a Google Cloud Storage bucket, enables versioning, and sets IAM policy.

    Returns True if created, False if cancelled.
    """
    click.echo(f"  - {'Status'.ljust(12)}: Not found")
    click.echo(f"  - {'Project'.ljust(12)}: {project_id}")
    _log_resolved_value("Location", location, location == DEFAULT_BUCKET_LOCATION)

    if not _confirm("Create this bucket?", default=True):
        return False

    click.secho(
        f"  Creating bucket gs://{bucket_name} in project {project_id} with location {location}...",
        fg="bright_black",
    )
    new_bucket = storage_client.create_bucket(bucket_name, location=location)
    new_bucket.iam_configuration.uniform_bucket_level_access_enabled = True
    new_bucket.versioning_enabled = True
    new_bucket.patch()
    click.secho("  Enabling versioning...", fg="bright_black")
    click.secho("  Configuring bucket IAM policy...", fg="bright_black")
    policy = new_bucket.get_iam_policy(requested_policy_version=3)
    policy["roles/storage.objectAdmin"].add(f"projectEditor:{project_id}")
    policy["roles/storage.objectAdmin"].add(f"projectOwner:{project_id}")
    new_bucket.set_iam_policy(policy)
    return True


def _abort_bucket_setup(is_default: bool):
    click.secho(
        "  No bucket available for remote Terraform state storage. Cancelling setup.",
        fg="red",
    )
    if is_default:
        click.secho(
            "  Hint: Use --no-tf-remote-state to keep Terraform state local, or --tf-state-bucket to override the bucket name. See --help for more.",
            fg="bright_black",
        )
    # Use sys.exit(1) instead of click.Abort() to avoid being caught by broad
    # except Exception blocks in the caller and to avoid Click's "Aborted!" message.
    sys.exit(1)


def _ensure_bucket_ready(
    storage_client,
    bucket_name: str,
    project_id: str,
    location: str = DEFAULT_BUCKET_LOCATION,
    is_default: bool = False,
) -> bool:
    """Checks if bucket exists and is ready to use, or creates it if missing.

    Returns True if the bucket is ready to use, False if the user wants to try another name.
    """
    try:
        bucket = storage_client.get_bucket(bucket_name)
        click.echo(f"  - {'Status'.ljust(12)}: Found")
        # Only prompt to reuse if it was the default bucket
        if is_default:
            if not _confirm("Use this bucket?", default=True):
                _abort_bucket_setup(is_default)
        else:
            click.echo("  Proceeding...")
        return True
    except exceptions.NotFound:
        if _create_and_configure_bucket(
            storage_client, bucket_name, project_id, location
        ):
            return True
        else:
            _abort_bucket_setup(is_default)


def _configure_remote_state(
    project_id: str,
    instance_name: str,
    bucket_name: str = "",
    location: str = DEFAULT_BUCKET_LOCATION,
) -> str:
    """Handles Google Cloud Storage state bucket verification, creation, and IAM setup."""
    try:
        storage_client = storage.Client(project=project_id)
    except Exception as e:
        raise click.ClickException(
            f"Failed to initialize Google Cloud Storage client for project '{project_id}': {e}. "
            "Ensure you are authenticated via 'gcloud auth application-default login'."
        )

    is_default = False
    if not bucket_name:
        bucket_name = _get_default_bucket_name(instance_name, project_id)
        is_default = True

    click.echo(
        "Setting up Google Cloud Storage bucket for storing terraform state remotely:"
    )
    _log_resolved_value("Name", bucket_name, is_default)

    try:
        ready = _ensure_bucket_ready(
            storage_client, bucket_name, project_id, location, is_default
        )
    except exceptions.Unauthorized as e:
        raise click.ClickException(
            f"Authentication failed: {e}\n"
            "Please ensure you are authenticated. Run 'gcloud auth application-default login' and try again."
        )
    except exceptions.Forbidden as e:
        raise click.ClickException(
            f"Permission denied: {e}\n"
            f"Please ensure your account has 'Storage Admin' or 'Project Editor' permissions in project '{project_id}'."
        )
    except click.Abort:
        click.echo("")
        sys.exit(1)
    except Exception as e:
        click.secho(
            f"  Error: Failed to access or create bucket gs://{bucket_name}.",
            fg="red",
            bold=True,
        )
        click.secho(f"  {e}", fg="red")
        raise click.ClickException("Setup cancelled.")

    if not ready:
        raise click.ClickException("Setup cancelled.")
    return bucket_name
