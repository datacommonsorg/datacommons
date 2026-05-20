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
import urllib.request
from typing import Any, Tuple

import click
from google.api_core import exceptions
from google.cloud import storage

from datacommons_admin.infra_templates import (
    BACKEND_TF_TEMPLATE,
    README_TEMPLATE,
    REMOTE_STATE_TEMPLATE,
)


def _create_and_configure_bucket(
    storage_client, bucket_name: str, project_id: str, location: str = "US"
):
    """Creates a GCS bucket, enables versioning, and sets IAM policy."""
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


def _ensure_bucket_ready(
    storage_client,
    bucket_name: str,
    project_id: str,
    location: str = "US",
    is_default: bool = False,
) -> bool:
    """Checks if bucket exists and is ready to use, or creates it if missing.

    Returns True if the bucket is ready to use, False if the user wants to try another name.
    """
    try:
        bucket = storage_client.get_bucket(bucket_name)
        click.echo("    Status:   Found")
        # Only prompt to reuse if it was the default bucket
        if is_default:
            click.secho("    [?]", fg="cyan", bold=True, nl=False)
            if not click.confirm(" Use this bucket?", default=True):
                click.secho("  Cancelling setup", fg="yellow")
                if is_default:
                    click.secho(
                        "  Hint: Use --no-tf-remote-state for local, or --tf-state-bucket to customize. See --help for more.",
                        fg="bright_black",
                    )
                import sys

                sys.exit(1)
        else:
            click.echo("  Proceeding...")
        return True
    except exceptions.NotFound:
        click.echo("    Status:   Not found")
        click.echo(f"  - Project:  {project_id}")
        if location == "US":
            click.echo(f"  - Location: {location} (Default)")
        else:
            click.secho("  ✔", fg="green", nl=False)
            click.echo(f" Location: {location} (from flag)")

        click.secho("    [?]", fg="cyan", bold=True, nl=False)
        if click.confirm(" Create this bucket?", default=True):
            _create_and_configure_bucket(
                storage_client, bucket_name, project_id, location
            )
            return True
        else:
            click.secho("  Cancelling setup", fg="yellow")
            if is_default:
                click.secho(
                    "  Hint: Use --no-tf-remote-state for local, or --tf-state-bucket to customize. See --help for more.",
                    fg="bright_black",
                )
            import sys

            sys.exit(1)


def _configure_remote_state(
    project_id: str, namespace: str, bucket_name: str = "", location: str = "US"
) -> str:
    """Handles GCS state bucket verification, creation, and IAM setup."""
    try:
        storage_client = storage.Client(project=project_id)
    except Exception as e:
        raise click.ClickException(
            f"Failed to initialize GCS client for project '{project_id}': {e}. "
            "Ensure you are authenticated via 'gcloud auth application-default login'."
        )

    is_default = False
    if not bucket_name:
        bucket_name = f"tf-state-{namespace}-{project_id}"
        is_default = True

    click.echo("Setting up GCS Bucket for storing terraform state remotely:")
    if is_default:
        click.echo(f"  - Name:     {bucket_name} (Default)")
    else:
        click.secho("  ✔", fg="green", nl=False)
        click.echo(f" Name:     {bucket_name} (from flag)")

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
    base_url = (
        f"https://raw.githubusercontent.com/datacommonsorg/datacommons/{ref}/infra/dcp"
    )

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


@admin.command()
@click.option(
    "--project-id", default="", help="GCP project id to initialize into tfvars."
)
@click.option(
    "--namespace", default="", help="Namespace prefix for provisioned resources."
)
@click.option("--dc-api-key", default="", help="Data Commons API key.")
@click.option(
    "--ref", default="main", show_default=True, help="Git ref for module source."
)
@click.option(
    "--force", is_flag=True, help="Overwrite existing generated files if present."
)
@click.option(
    "--tf-remote-state/--no-tf-remote-state",
    default=True,
    help="Enable or disable Terraform remote state management in GCS.",
)
@click.option(
    "--tf-state-bucket",
    default="",
    help="Explicit GCS bucket name for Terraform remote state.",
)
@click.option(
    "--tf-state-bucket-location",
    default="US",
    help="GCS bucket location if a new bucket needs to be created.",
)
@click.option(
    "--tf-state-prefix",
    default="",
    help="GCS object prefix for Terraform state file (default: terraform/state/{namespace}).",
)
def init(
    project_id: str,
    namespace: str,
    dc_api_key: str,
    ref: str,
    force: bool,
    tf_remote_state: bool,
    tf_state_bucket: str,
    tf_state_bucket_location: str,
    tf_state_prefix: str,
) -> None:
    """Initialize Terraform scaffolding for Data Commons administration/infrastructure."""
    click.secho("Datacommons Admin Init", fg="cyan", bold=True)

    click.secho("\n[Project Configuration]", fg="cyan", bold=True)
    click.secho("Configuring project settings...", fg="bright_black")
    if project_id:
        click.secho("  ✔", fg="green", nl=False)
        click.echo(f" Project ID: {project_id} (from flag)")
    if namespace:
        click.secho("  ✔", fg="green", nl=False)
        click.echo(f" Namespace:  {namespace} (from flag)")

    resolved_project_id = project_id.strip()
    if not resolved_project_id:
        click.secho("  [?]", fg="cyan", bold=True, nl=False)
        resolved_project_id = click.prompt(
            " GCP project id",
            type=str,
        ).strip()
    if not resolved_project_id:
        raise click.ClickException("GCP project id must not be empty.")

    resolved_namespace = namespace.strip()
    while True:
        if not resolved_namespace:
            click.secho("  [?]", fg="cyan", bold=True, nl=False)
            resolved_namespace = click.prompt(
                " Namespace",
                type=str,
            ).strip()
            if not resolved_namespace:
                click.secho("Error: Namespace must not be empty.", fg="red")
                continue

        target_dir = Path.cwd() / resolved_namespace
        if target_dir.exists() and not force:
            click.secho(
                f"Error: Folder '{resolved_namespace}' already exists locally. "
                "Please specify a different namespace, or use --force to overwrite.",
                fg="yellow",
            )
            resolved_namespace = ""
            continue

        break

    main_tf_path = target_dir / "main.tf"
    tfvars_path = target_dir / "terraform.tfvars"
    readme_path = target_dir / "README.md"
    backend_tf_path = target_dir / "backend.tf"

    use_remote_state = tf_remote_state
    click.secho("\n[Terraform Backend Setup]", fg="cyan", bold=True)
    click.secho("Configuring backend for Terraform state...", fg="bright_black")
    if not tf_remote_state:
        click.echo("  Using local backend for Terraform state.")

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

    resolved_bucket_name = (
        _configure_remote_state(
            resolved_project_id,
            resolved_namespace,
            tf_state_bucket,
            tf_state_bucket_location,
        )
        if use_remote_state
        else ""
    )

    click.secho("\n[Terraform Starter Files]", fg="cyan", bold=True)
    click.secho(
        "Downloading templates and populating configuration files...", fg="bright_black"
    )

    resolved_dc_api_key = dc_api_key.strip()
    if not resolved_dc_api_key:
        click.secho("  [?]", fg="cyan", bold=True, nl=False)
        resolved_dc_api_key = click.prompt(
            " Data Commons API key (from apikeys.datacommons.org)",
            type=str,
            default="",
            show_default=False,
        ).strip()

        if not resolved_dc_api_key:
            click.secho(
                "  [!] Warning: Data Commons API key was skipped. You must add it to terraform.tfvars before running terraform apply.",
                fg="yellow",
                bold=True,
            )

    target_dir.mkdir(parents=True, exist_ok=True)
    click.secho(f"Creating directory: {target_dir}", fg="cyan")

    resolved_tf_state_prefix = (
        tf_state_prefix.strip() or f"terraform/state/{resolved_namespace}"
    )

    try:
        variables_content, main_content, outputs_content, tfvars_example = (
            _get_github_templates(ref)
        )

        # Update the stack module source to point to GitHub
        resolved_source = f"git::https://github.com/datacommonsorg/datacommons.git//infra/dcp/modules/stack?ref={ref}"
        main_content = re.sub(
            r'source\s*=\s*["\']\./modules/stack["\']',
            f'source = "{resolved_source}"',
            main_content,
        )

        # Write the files
        (target_dir / "variables.tf").write_text(variables_content, encoding="utf-8")
        main_tf_path.write_text(main_content, encoding="utf-8")
        (target_dir / "outputs.tf").write_text(outputs_content, encoding="utf-8")
        # Modify tfvars_example with actual values
        tfvars_content = tfvars_example
        tfvars_content = tfvars_content.replace(
            '"$$PROJECT_ID$$"', f'"{resolved_project_id}"'
        )
        tfvars_content = tfvars_content.replace(
            '"$$NAMESPACE$$"', f'"{resolved_namespace}"'
        )
        if resolved_dc_api_key:
            tfvars_content = tfvars_content.replace(
                '"$$DC_API_KEY$$"', f'"{resolved_dc_api_key}"'
            )

        (target_dir / "terraform.tfvars").write_text(tfvars_content, encoding="utf-8")

    except Exception as e:
        raise click.ClickException(f"Failed to initialize Terraform templates: {e}")

    remote_state_info = ""
    if use_remote_state and resolved_bucket_name:
        remote_state_info = REMOTE_STATE_TEMPLATE.format(
            bucket_name=resolved_bucket_name, prefix=resolved_tf_state_prefix
        )

    readme_path.write_text(
        README_TEMPLATE.format(remote_state_section=remote_state_info), encoding="utf-8"
    )
    if use_remote_state and resolved_bucket_name:
        backend_tf_path.write_text(
            BACKEND_TF_TEMPLATE.format(
                bucket_name=resolved_bucket_name,
                prefix=resolved_tf_state_prefix,
            ),
            encoding="utf-8",
        )

    click.secho("Downloaded and populated Terraform templates.", fg="green")

    click.secho(f"\nCustomize variables in {resolved_namespace}/terraform.tfvars as needed.", fg="bright_black")
    click.secho(f"Refer to {resolved_namespace}/README.md for more info and next steps.", fg="bright_black")


def _setup_ingestion_client() -> Tuple[Any, str, str]:
    click.secho(
        "Fetching Ingestion Helper URI, Orchestrator Service Account, and Spanner details from Terraform outputs...",
        fg="bright_black",
    )

    from datacommons_admin.tf_utils import (
        get_dcp_ingestion_helper_uri,
        get_dcp_orchestrator_service_account_email,
        get_dcp_spanner_instance_id,
        get_dcp_spanner_database_id,
    )
    from datacommons_admin.ingestion_helper_client import IngestionHelperClient

    uri = get_dcp_ingestion_helper_uri()
    sa_email = get_dcp_orchestrator_service_account_email()
    instance_id = get_dcp_spanner_instance_id()
    database_id = get_dcp_spanner_database_id()

    click.secho(f"Found Ingestion Helper URI: {uri}", fg="green")
    click.secho(f"Found Orchestrator Service Account: {sa_email}", fg="green")
    click.secho(
        f"Found Spanner Database Instance: {instance_id} / Database ID: {database_id}",
        fg="green",
    )

    client = IngestionHelperClient(uri, service_account_email=sa_email)
    return client, instance_id, database_id


def _run_seed_db(client: Any, instance_id: str, database_id: str) -> None:
    click.secho(
        f"Seeding Spanner database '{instance_id}/{database_id}' via the Ingestion Helper service (this may take a few moments)...",
        fg="bright_black",
    )
    result = client.seed_database()
    click.secho("Successfully seeded Spanner database!", fg="green", bold=True)
    if "message" in result:
        click.secho(f"Details: {result['message']}", fg="bright_black")


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
    if "message" in result:
        click.secho(f"Details: {result['message']}", fg="bright_black")

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
