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

from pathlib import Path
import re
import sys
import urllib.request
from typing import Any, Tuple

import click
from google.api_core import exceptions
from google.cloud import storage

from . import __version__
from datacommons_admin.infra_templates import (
    BACKEND_TF_TEMPLATE,
    README_TEMPLATE,
    REMOTE_STATE_TEMPLATE,
)


DEFAULT_BUCKET_LOCATION = "US"
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/datacommonsorg/datacommons"
GITHUB_REPO_URL = "https://github.com/datacommonsorg/datacommons.git"


def _get_default_bucket_name(instance_name: str, project_id: str) -> str:
    """Returns the default Google Cloud Storage bucket name for Terraform state."""
    return f"tf-state-{instance_name}-{project_id}"


def _get_default_state_prefix(instance_name: str) -> str:
    """Returns the default Google Cloud Storage object prefix for Terraform state."""
    return f"terraform/state/{instance_name}"


def _log_resolved_value(label: str, value: str, is_default: bool, indent: int = 2):
    """Logs a value with a bullet if default, or a green checkmark if from flag."""
    prefix = " " * indent
    padded_label = label.ljust(12)
    if is_default:
        click.echo(f"{prefix}- {padded_label}: {value} (Default)")
    else:
        click.secho(f"{prefix}✔", fg="green", nl=False)
        click.echo(f" {padded_label}: {value} (from flag)")


def _prompt(text: str, indent: int = 2, **kwargs):
    """Prints the cyan [?] prompt symbol and calls click.prompt."""
    click.secho(" " * indent + "[?]", fg="cyan", bold=True, nl=False)
    prompt_text = text if text.startswith(" ") else f" {text}"
    return click.prompt(prompt_text, **kwargs)


def _confirm(text: str, indent: int = 2, **kwargs):
    """Prints the cyan [?] prompt symbol and calls click.confirm."""
    click.secho(" " * indent + "[?]", fg="cyan", bold=True, nl=False)
    prompt_text = text if text.startswith(" ") else f" {text}"
    return click.confirm(prompt_text, **kwargs)


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
    click.secho(f"  Enabling versioning...", fg="bright_black")
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


def _get_github_templates(ref: str) -> tuple[str, str, str, str]:
    """Fetches variables.tf, main.tf, outputs.tf, and terraform.tfvars.template from GitHub for the given ref."""
    base_url = f"{GITHUB_RAW_BASE_URL}/{ref}/infra/dcp"

    def fetch(filename: str) -> str:
        url = f"{base_url}/{filename}"

        req = urllib.request.Request(url, headers={"User-Agent": "DataCommons-CLI"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8")

    return (
        fetch("variables.tf"),
        fetch("main.tf"),
        fetch("outputs.tf"),
        fetch("terraform.tfvars.template"),
    )


@click.group()
def admin() -> None:
    """Manage a Data Commons Platform instance in Google Cloud"""


def _validate_instance_name(instance_name: str) -> Tuple[bool, str]:
    if not instance_name:
        return False, "Instance name must not be empty."
    if len(instance_name) > 16:
        return (
            False,
            f"Instance name must be 16 characters or less (currently {len(instance_name)} characters).",
        )
    if not re.match(r"^[a-z]([-a-z0-9]*[a-z0-9])?$", instance_name):
        return (
            False,
            "Instance name must start with a lowercase letter, end with a lowercase letter or number, and contain only lowercase alphanumeric characters and dashes.",
        )
    return True, ""


def _resolve_project_config(
    project_id: str, instance_name: str, force: bool
) -> Tuple[str, str, Path]:
    """Resolves project ID and instance name, and determines target directory."""
    if project_id:
        _log_resolved_value("Project ID", project_id, is_default=False)
    if instance_name:
        _log_resolved_value("Instance Name", instance_name, is_default=False)

    resolved_project_id = project_id.strip()
    if not resolved_project_id:
        resolved_project_id = _prompt(
            "Google Cloud Platform project ID", type=str
        ).strip()
    if not resolved_project_id:
        raise click.ClickException("GCP project ID must not be empty.")

    resolved_instance_name = instance_name.strip()
    if resolved_instance_name:
        is_valid, err_msg = _validate_instance_name(resolved_instance_name)
        if not is_valid:
            raise click.ClickException(err_msg)

    while True:
        if not resolved_instance_name:
            resolved_instance_name = _prompt("Instance Name", type=str).strip()
            is_valid, err_msg = _validate_instance_name(resolved_instance_name)
            if not is_valid:
                click.secho(f"Error: {err_msg}", fg="red")
                resolved_instance_name = ""
                continue

        target_dir = Path.cwd() / resolved_instance_name
        if target_dir.exists() and not force:
            click.secho(
                f"Error: Folder '{resolved_instance_name}' already exists locally. "
                "Please specify a different instance name, or use --force to overwrite.",
                fg="yellow",
            )
            resolved_instance_name = ""
            continue

        break

    return resolved_project_id, resolved_instance_name, target_dir


def _check_existing_files(target_dir: Path, use_remote_state: bool, force: bool):
    """Checks if target files already exist and raises error if they do (and not force)."""
    main_tf_path = target_dir / "main.tf"
    tfvars_path = target_dir / "terraform.tfvars"
    readme_path = target_dir / "README.md"
    backend_tf_path = target_dir / "backend.tf"

    paths_to_check = [main_tf_path, tfvars_path, readme_path]
    if use_remote_state:
        paths_to_check.append(backend_tf_path)

    existing_paths = [path for path in paths_to_check if path.exists()]
    if existing_paths and not force:
        existing_labels = ", ".join(str(path) for path in existing_paths)
        raise click.ClickException(
            f"Refusing to overwrite existing file(s): {existing_labels}. "
            "Use --force to overwrite."
        )


def _setup_dcp_config_dir(
    target_dir: Path,
    project_id: str,
    instance_name: str,
    bucket_name: str,
    tf_state_prefix: str,
    dc_api_key: str,
    ref: str,
    use_remote_state: bool,
):
    """Downloads and populates Terraform templates."""

    api_key = dc_api_key.strip()
    if not api_key:
        api_key = _prompt(
            "Data Commons API key (from apikeys.datacommons.org)",
            type=str,
            default="",
            show_default=False,
        ).strip()

        if not api_key:
            click.secho(
                "  [!] Warning: Data Commons API key was skipped. You must add it to terraform.tfvars before running terraform apply.",
                fg="yellow",
                bold=True,
            )

    target_dir.mkdir(parents=True, exist_ok=True)
    click.secho(f"Creating directory: {target_dir}", fg="bright_black")

    try:
        variables_content, main_content, outputs_content, tfvars_example = (
            _get_github_templates(ref)
        )

        # Update the stack module source to point to GitHub
        resolved_source = f"git::{GITHUB_REPO_URL}//infra/dcp/modules/stack?ref={ref}"
        main_content = re.sub(
            r'source\s*=\s*["\']\./modules/stack["\']',
            f'source = "{resolved_source}"',
            main_content,
        )

        # Write the files
        (target_dir / "variables.tf").write_text(variables_content, encoding="utf-8")
        (target_dir / "main.tf").write_text(main_content, encoding="utf-8")
        (target_dir / "outputs.tf").write_text(outputs_content, encoding="utf-8")

        # Modify tfvars_example with actual values
        tfvars_content = tfvars_example
        tfvars_content = tfvars_content.replace('"$$PROJECT_ID$$"', f'"{project_id}"')
        tfvars_content = tfvars_content.replace('"$$INSTANCE_NAME$$"', f'"{instance_name}"')
        if api_key:
            tfvars_content = tfvars_content.replace('"$$DC_API_KEY$$"', f'"{api_key}"')

        (target_dir / "terraform.tfvars").write_text(tfvars_content, encoding="utf-8")

    except Exception as e:
        raise click.ClickException(f"Failed to initialize Terraform templates: {e}")

    remote_state_info = ""
    if use_remote_state and bucket_name:
        remote_state_info = REMOTE_STATE_TEMPLATE.format(
            bucket_name=bucket_name, prefix=tf_state_prefix
        )

    (target_dir / "README.md").write_text(
        README_TEMPLATE.format(remote_state_section=remote_state_info), encoding="utf-8"
    )
    if use_remote_state and bucket_name:
        (target_dir / "backend.tf").write_text(
            BACKEND_TF_TEMPLATE.format(
                bucket_name=bucket_name,
                prefix=tf_state_prefix,
            ),
            encoding="utf-8",
        )

    click.secho("Downloaded and populated Terraform templates.", fg="bright_black")


@admin.command()
@click.option(
    "--project-id",
    default="",
    help="Google Cloud Platform project ID used for all resources related to your Data Commons instance.",
)
@click.option(
    "--instance-name", default="", help="Instance name that serves as prefix for provisioned resources."
)
@click.option("--dc-api-key", default="", help="Data Commons API key.")
@click.option(
    "--tf-git-ref",
    default=f"v{__version__}",
    show_default=True,
    help="Git ref for module source.",
)
@click.option(
    "--force", is_flag=True, help="Overwrite existing generated files if present."
)
@click.option(
    "--tf-remote-state/--no-tf-remote-state",
    default=True,
    help="Enable or disable Terraform remote state management in Google Cloud Storage. Disabling ignores other --tf-state-* flags.",
)
@click.option(
    "--tf-state-bucket",
    default="",
    help="Google Cloud Storage bucket for Terraform remote state. Generates a default name if omitted. Prompts to create the bucket if it is missing.",
)
@click.option(
    "--tf-state-bucket-location",
    default=DEFAULT_BUCKET_LOCATION,
    show_default=True,
    help="Google Cloud Storage bucket location if a new bucket needs to be created.",
)
@click.option(
    "--tf-state-prefix",
    default="",
    help="Google Cloud Storage object prefix for Terraform state file (default: terraform/state/{instance_name}).",
)
def init(
    project_id: str,
    instance_name: str,
    dc_api_key: str,
    tf_git_ref: str,
    force: bool,
    tf_remote_state: bool,
    tf_state_bucket: str,
    tf_state_bucket_location: str,
    tf_state_prefix: str,
) -> None:
    """Initialize Terraform scaffolding for Data Commons administration/infrastructure."""
    click.secho("Data Commons Admin Init", fg="cyan", bold=True)

    # 1. Project Configs
    click.secho("\n[Project configuration]", fg="cyan", bold=True)
    click.secho("Configuring project settings...", fg="bright_black")
    resolved_project_id, resolved_instance_name, target_dir = _resolve_project_config(
        project_id, instance_name, force
    )

    # 2. Terraform Setup
    click.secho("\n[Terraform backend setup]", fg="cyan", bold=True)
    click.secho("Configuring backend for Terraform state...", fg="bright_black")
    if not tf_remote_state:
        click.echo("  Using local backend for Terraform state.")

    # Refuse to overwrite existing files unless --force is specified
    _check_existing_files(target_dir, tf_remote_state, force)

    resolved_bucket_name = (
        _configure_remote_state(
            resolved_project_id,
            resolved_instance_name,
            tf_state_bucket,
            tf_state_bucket_location,
        )
        if tf_remote_state
        else ""
    )

    resolved_tf_state_prefix = tf_state_prefix.strip() or _get_default_state_prefix(
        resolved_instance_name
    )

    # 3. DCP config dir setup
    click.secho("\n[DCP configuration]", fg="cyan", bold=True)
    click.secho("Setting up configuration files...", fg="bright_black")
    _setup_dcp_config_dir(
        target_dir,
        resolved_project_id,
        resolved_instance_name,
        resolved_bucket_name,
        resolved_tf_state_prefix,
        dc_api_key,
        tf_git_ref,
        tf_remote_state,
    )

    click.secho(
        f"Customize variables in {resolved_instance_name}/terraform.tfvars as needed.",
        fg="green",
    )
    click.secho(
        "Refer to documentation for more info and next steps.",
        fg="green",
    )


def _setup_ingestion_client() -> Tuple[Any, str, str]:
    click.secho(
        "Fetching ingestion service URL, workflow service account, and Spanner details from Terraform outputs...",
        fg="bright_black",
    )

    from datacommons_admin.tf_utils import (
        get_ingestion_service_url,
        get_ingestion_workflow_service_account_email,
        get_spanner_instance_id,
        get_spanner_database_id,
    )
    from datacommons_admin.ingestion_helper_client import IngestionHelperClient

    url = get_ingestion_service_url()
    sa_email = get_ingestion_workflow_service_account_email()
    instance_id = get_spanner_instance_id()
    database_id = get_spanner_database_id()

    click.secho(f"Found ingestion service URL: {url}", fg="green")
    click.secho(f"Found ingestion workflow service account: {sa_email}", fg="green")
    click.secho(
        f"Found Spanner instance ID: {instance_id} / database ID: {database_id}",
        fg="green",
    )

    client = IngestionHelperClient(url, service_account_email=sa_email)
    return client, instance_id, database_id


def _run_seed_db(client: Any, instance_id: str, database_id: str) -> None:
    click.secho(
        f"Seeding Spanner database '{instance_id}/{database_id}' via the Ingestion Helper service (this may take a few moments)...",
        fg="bright_black",
    )
    result = client.seed_database()
    click.secho("Successfully seeded Spanner database!", fg="green", bold=True)
    message = result.get("message")
    if message:
        click.secho(f"Details: {message}", fg="bright_black")


@admin.command(name="init-db")
@click.option(
    "--init-only", is_flag=True, help="Only initialize the database without seeding."
)
def init_db(init_only: bool) -> None:
    """Initialize (and by default seed) the Spanner database via the DCP Ingestion Helper service."""
    click.secho("Datacommons Admin Init-DB", fg="cyan", bold=True)
    client, instance_id, database_id = _setup_ingestion_client()

    click.secho(
        f"Initializing Spanner database '{instance_id}/{database_id}' via the Ingestion Helper service (this may take a few moments)...",
        fg="bright_black",
    )
    result = client.initialize_database()

    click.secho("Successfully initialized Spanner database!", fg="green", bold=True)
    message = result.get("message")
    if message:
        click.secho(f"Details: {message}", fg="bright_black")

    if not init_only:
        _run_seed_db(client, instance_id, database_id)


@admin.command(name="seed-db")
def seed_db() -> None:
    """Seed the Spanner database via the DCP Ingestion Helper service."""
    click.secho("Datacommons Admin Seed-DB", fg="cyan", bold=True)
    client, instance_id, database_id = _setup_ingestion_client()
    _run_seed_db(client, instance_id, database_id)


from datacommons_admin.ingest_cli import ingest

admin.add_command(ingest)
