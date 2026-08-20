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
from unittest.mock import patch

from click.testing import CliRunner
from datacommons_admin import __version__
from datacommons_admin.admin_cli import admin


@patch("datacommons_admin.init.utils.scaffold_utils._get_github_templates")
def test_init_success_with_options(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "test-project",
                "--instance-name",
                "test-instance",
                "--dc-api-key",
                "test-key",
                "--no-tf-remote-state",
            ],
        )
        assert result.exit_code == 0
        assert "Downloaded and populated Terraform templates." in result.output

        target_dir = Path.cwd() / "test-instance"
        assert target_dir.exists()
        assert (target_dir / "main.tf").exists()
        assert (target_dir / "terraform.tfvars").exists()
        assert (target_dir / "README.md").exists()
        assert not (target_dir / "backend.tf").exists()

        tfvars_content = (target_dir / "terraform.tfvars").read_text()
        assert 'project_id = "test-project"' in tfvars_content
        assert 'instance_name  = "test-instance"' in tfvars_content
        assert 'dc_api_key = "test-key"' in tfvars_content


@patch("datacommons_admin.init.utils.scaffold_utils._get_github_templates")
def test_init_success_with_deprecated_namespace_flag(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "test-project",
                "--namespace",
                "legacy-namespace",
                "--dc-api-key",
                "test-key",
                "--no-tf-remote-state",
            ],
        )
        assert result.exit_code == 0
        target_dir = Path.cwd() / "legacy-namespace"
        assert target_dir.exists()
        tfvars_content = (target_dir / "terraform.tfvars").read_text()
        assert 'instance_name  = "legacy-namespace"' in tfvars_content


@patch("datacommons_admin.init.utils.scaffold_utils._get_github_templates")
def test_init_success_with_prompts(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            ["init", "--no-tf-remote-state"],
            input="prompt-project\nprompt-instance\nprompt-key\n",
        )
        assert result.exit_code == 0
        target_dir = Path.cwd() / "prompt-instance"
        assert target_dir.exists()

        tfvars_content = (target_dir / "terraform.tfvars").read_text()
        assert 'project_id = "prompt-project"' in tfvars_content
        assert 'instance_name  = "prompt-instance"' in tfvars_content


@patch("datacommons_admin.init.utils.scaffold_utils._get_github_templates")
def test_init_existing_folder_force(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        existing_dir = Path.cwd() / "existing-dcp"
        existing_dir.mkdir()
        (existing_dir / "main.tf").write_text("old content")

        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "test-project",
                "--instance-name",
                "existing-dcp",
                "--force",
                "--no-tf-remote-state",
            ],
            input="test-key\n",
        )
        assert result.exit_code == 0
        assert "Downloaded and populated Terraform templates." in result.output

        main_tf = existing_dir / "main.tf"
        assert "old content" not in main_tf.read_text()
        assert 'module "stack"' in main_tf.read_text()


@patch("datacommons_admin.init.utils.scaffold_utils._get_github_templates")
@patch("datacommons_admin.init.init_cli._configure_remote_state")
def test_init_remote_state(
    mock_configure, mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    mock_configure.return_value = "mock-bucket-name"

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "remote-project",
                "--instance-name",
                "remote-instance",
                "--dc-api-key",
                "remote-key",
            ],
        )
        assert result.exit_code == 0
        mock_configure.assert_called_once_with(
            "remote-project", "remote-instance", "", "US"
        )

        target_dir = Path.cwd() / "remote-instance"
        assert (target_dir / "backend.tf").exists()
        backend_content = (target_dir / "backend.tf").read_text()
        assert 'bucket = "mock-bucket-name"' in backend_content


@patch("datacommons_admin.init.utils.scaffold_utils._get_github_templates")
def test_init_uses_default_ref_v_prefixed(
    mock_get_templates, runner: CliRunner, tmp_path: Path
) -> None:
    mock_get_templates.return_value = (
        'variable "test" {}',
        'module "stack" {\n  source = "./modules/stack"\n}',
        'output "test" {}',
        'project_id = "$$PROJECT_ID$$"\ninstance_name  = "$$INSTANCE_NAME$$"\n# dc_api_key = "$$DC_API_KEY$$"',
    )
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            admin,
            [
                "init",
                "--project-id",
                "ref-project",
                "--instance-name",
                "ref-instance",
                "--dc-api-key",
                "ref-key",
                "--no-tf-remote-state",
            ],
        )
        assert result.exit_code == 0
        mock_get_templates.assert_called_once_with(f"v{__version__}")
