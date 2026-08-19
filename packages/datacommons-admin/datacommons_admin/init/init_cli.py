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

import click

from datacommons_admin import __version__
from datacommons_admin.init.gcs_utils import (
    DEFAULT_BUCKET_LOCATION,
    _configure_remote_state,
    _get_default_state_prefix,
)
from datacommons_admin.init.scaffold_utils import (
    _check_existing_files,
    _resolve_project_config,
    _setup_dcp_config_dir,
)


@click.command()
@click.option(
    "--project-id",
    default="",
    help="Google Cloud Platform project ID used for all resources related to your Data Commons instance.",
)
@click.option(
    "--instance-name",
    "--namespace",
    default="",
    help="Instance name that serves as prefix for provisioned resources. (Deprecated alias: --namespace)",
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
