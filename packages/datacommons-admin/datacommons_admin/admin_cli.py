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
    TFVARS_TEMPLATE,
)


def _configure_remote_state(resolved_project_id: str, resolved_namespace: str) -> str:
    """Handles GCS state bucket verification, creation, and IAM setup."""
    default_bucket = f"tf-state-{resolved_namespace}-{resolved_project_id}"
    try:
        storage_client = storage.Client(project=resolved_project_id)
    except Exception as e:
        raise click.ClickException(
            f"Failed to initialize GCS client for project '{resolved_project_id}': {e}. "
            "Ensure you are authenticated via 'gcloud auth application-default login'."
        )

    while True:
        bucket_name = click.prompt(
            "Enter the name of your GCS Terraform State Bucket",
            type=str,
            default=default_bucket,
        ).strip()
        if not bucket_name:
            click.secho("Error: Bucket name cannot be empty.", fg="red")
            continue

        click.secho(f"Checking bucket gs://{bucket_name}...", fg="bright_black")
        try:
            bucket = storage_client.get_bucket(bucket_name)
            click.secho(f"Bucket gs://{bucket_name} already exists.", fg="yellow")
            reuse = click.confirm(
                f"Do you want to re-use the existing bucket gs://{bucket_name}?",
                default=True,
            )
            if reuse:
                return bucket_name
            else:
                click.secho(
                    "Please enter a different bucket name to continue.", fg="cyan"
                )
                continue
        except exceptions.NotFound:
            click.secho(
                f"Creating bucket gs://{bucket_name} in project {resolved_project_id}...",
                fg="bright_black",
            )
            try:
                new_bucket = storage_client.create_bucket(bucket_name, location="US")
                new_bucket.iam_configuration.uniform_bucket_level_access_enabled = True
                new_bucket.versioning_enabled = True
                new_bucket.patch()
                click.secho(
                    f"Enabling versioning on gs://{bucket_name}...", fg="bright_black"
                )

                click.secho(
                    "Configuring bucket IAM policy for project editors/owners...",
                    fg="bright_black",
                )
                policy = new_bucket.get_iam_policy(requested_policy_version=3)
                policy["roles/storage.objectAdmin"].add(
                    f"projectEditor:{resolved_project_id}"
                )
                policy["roles/storage.objectAdmin"].add(
                    f"projectOwner:{resolved_project_id}"
                )
                new_bucket.set_iam_policy(policy)

                return bucket_name
            except Exception as e:
                click.secho(
                    f"Error: Failed to create or access bucket gs://{bucket_name}.",
                    fg="red",
                    bold=True,
                )
                click.secho(str(e), fg="red")
                click.secho(
                    "Please verify permissions/names availability and try again.",
                    fg="yellow",
                )
                continue
        except Exception as e:
            click.secho(
                f"Error: Failed to access bucket gs://{bucket_name}.",
                fg="red",
                bold=True,
            )
            click.secho(str(e), fg="red")
            click.secho(
                "Please verify permissions/names availability and try again.",
                fg="yellow",
            )
            continue


def _get_github_templates(ref: str) -> tuple[str, str, str, str]:
    """Fetches variables.tf, main.tf, outputs.tf, and terraform.tfvars.example from GitHub for the given ref."""
    base_url = (
        f"https://raw.githubusercontent.com/datacommonsorg/datacommons/{ref}/infra/dcp"
    )

    def fetch(filename: str) -> str:
        url = f"{base_url}/{filename}"
        click.secho(f"Downloading {filename} from GitHub ({ref})...", fg="bright_black")
        req = urllib.request.Request(url, headers={"User-Agent": "DataCommons-CLI"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8")

    return (
        fetch("variables.tf"),
        fetch("main.tf"),
        fetch("outputs.tf"),
        fetch("terraform.tfvars.example"),
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
def init(
    project_id: str,
    namespace: str,
    dc_api_key: str,
    ref: str,
    force: bool,
) -> None:
    """Initialize Terraform scaffolding for Data Commons administration/infrastructure."""
    click.secho("Datacommons Admin Init", fg="cyan", bold=True)
    click.secho("Generating Terraform starter files...", fg="bright_black")

    resolved_project_id = (
        project_id.strip()
        or click.prompt("GCP project id", type=str, prompt_suffix=": ").strip()
    )
    if not resolved_project_id:
        raise click.ClickException("GCP project id must not be empty.")

    resolved_namespace = namespace.strip()
    while True:
        if not resolved_namespace:
            resolved_namespace = click.prompt(
                "Namespace", type=str, prompt_suffix=": "
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

    resolved_dc_api_key = (
        dc_api_key.strip()
        or click.prompt(
            "Data Commons API key (get one at apikeys.datacommons.org)",
            type=str,
            default="",
            show_default=False,
            prompt_suffix=": ",
        ).strip()
    )

    main_tf_path = target_dir / "main.tf"
    tfvars_path = target_dir / "terraform.tfvars"
    readme_path = target_dir / "README.md"
    backend_tf_path = target_dir / "backend.tf"

    use_remote_state = click.confirm(
        "Do you want to configure remote state storage in GCS?", default=False
    )

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
        _configure_remote_state(resolved_project_id, resolved_namespace)
        if use_remote_state
        else ""
    )

    target_dir.mkdir(parents=True, exist_ok=True)

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

        click.secho(f"- Wrote {target_dir / 'variables.tf'}", fg="bright_black")
        click.secho(f"- Wrote {target_dir / 'outputs.tf'}", fg="bright_black")
        click.secho(f"- Wrote {tfvars_path}", fg="bright_black")

    except Exception as e:
        raise click.ClickException(f"Failed to initialize Terraform templates: {e}")

    remote_state_info = ""
    if use_remote_state and resolved_bucket_name:
        remote_state_info = REMOTE_STATE_TEMPLATE.format(
            bucket_name=resolved_bucket_name
        )

    readme_path.write_text(
        README_TEMPLATE.format(remote_state_section=remote_state_info), encoding="utf-8"
    )
    if use_remote_state and resolved_bucket_name:
        backend_tf_path.write_text(
            BACKEND_TF_TEMPLATE.format(bucket_name=resolved_bucket_name),
            encoding="utf-8",
        )

    click.secho(f"Initialized Terraform scaffold in {target_dir}", fg="green")
    click.secho(f"- Wrote {main_tf_path}", fg="bright_black")
    click.secho(f"- Wrote {tfvars_path}", fg="bright_black")
    click.secho(f"- Wrote {readme_path}", fg="bright_black")
    if use_remote_state and resolved_bucket_name:
        click.secho(f"- Wrote {backend_tf_path}", fg="bright_black")
    click.secho(
        f"Generated new folder '{resolved_namespace}'. See {resolved_namespace}/README.md for next steps.",
        fg="cyan",
    )


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
