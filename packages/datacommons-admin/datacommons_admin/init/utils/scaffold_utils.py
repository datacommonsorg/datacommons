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
from typing import Tuple
import urllib.request

import click

from datacommons_admin.init.utils.infra_templates import (
    BACKEND_TF_TEMPLATE,
    README_TEMPLATE,
    REMOTE_STATE_TEMPLATE,
)
from datacommons_admin.shared_utils.ui_utils import (
    _log_resolved_value,
    _prompt,
)


GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/datacommonsorg/datacommons"
GITHUB_REPO_URL = "https://github.com/datacommonsorg/datacommons.git"


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
        tfvars_content = tfvars_content.replace(
            '"$$INSTANCE_NAME$$"', f'"{instance_name}"'
        )
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
