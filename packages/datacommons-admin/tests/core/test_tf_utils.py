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

from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner
from datacommons_admin.admin_cli import admin
from datacommons_admin.core.utils.tf_utils import (
    get_project_id,
    get_spanner_instance_id,
    get_terraform_output,
)
from google.cloud.exceptions import Forbidden, NotFound


@patch("google.cloud.storage.Client")
def test_get_terraform_output_from_gcs_project_and_instance(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client = MagicMock()
    mock_storage_client.return_value = mock_client
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_text.return_value = (
        '{"outputs": {"test_key": {"value": "resolved-val"}}}'
    )

    @admin.command(name="test-gcs-proj-inst")
    def test_cmd() -> None:
        val = get_terraform_output("test_key")
        click.echo(f"VAL={val}")

    result = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-proj",
            "--instance-name",
            "mock-inst",
            "test-gcs-proj-inst",
        ],
    )
    assert result.exit_code == 0
    assert "VAL=resolved-val" in result.output
    mock_storage_client.assert_called_with(project="mock-proj")
    mock_client.bucket.assert_called_once_with("tf-state-mock-inst-mock-proj")
    mock_bucket.blob.assert_called_once_with(
        "terraform/state/mock-inst/default.tfstate"
    )


@patch("google.cloud.storage.Client")
def test_get_terraform_output_from_gcs_explicit_location(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client = MagicMock()
    mock_storage_client.return_value = mock_client
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_text.return_value = (
        '{"outputs": {"test_key": {"value": "custom-val"}}}'
    )

    @admin.command(name="test-gcs-explicit")
    def test_cmd() -> None:
        val = get_terraform_output("test_key")
        click.echo(f"VAL={val}")

    # Explicit URI with file
    result = runner.invoke(
        admin,
        [
            "--tf-state-location",
            "gs://my-bucket/custom/state.tfstate",
            "test-gcs-explicit",
        ],
    )
    assert result.exit_code == 0
    assert "VAL=custom-val" in result.output
    mock_client.bucket.assert_called_with("my-bucket")
    mock_bucket.blob.assert_called_with("custom/state.tfstate")

    # Explicit URI with directory (auto appends default.tfstate)
    result_dir = runner.invoke(
        admin,
        [
            "--tf-state-location",
            "gs://my-bucket/custom",
            "test-gcs-explicit",
        ],
    )
    assert result_dir.exit_code == 0
    mock_bucket.blob.assert_called_with("custom/default.tfstate")


def test_get_terraform_output_invalid_gcs_uri(runner: CliRunner) -> None:
    @admin.command(name="test-invalid-uri")
    def test_cmd() -> None:
        get_terraform_output("test_key")

    result = runner.invoke(
        admin,
        [
            "--tf-state-location",
            "https://storage.googleapis.com/bad/uri",
            "test-invalid-uri",
        ],
    )
    assert result.exit_code != 0
    assert "Invalid GCS URI" in result.output


@patch("google.cloud.storage.Client")
def test_get_terraform_output_from_gcs_not_found(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client = MagicMock()
    mock_storage_client.return_value = mock_client
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_text.side_effect = NotFound("404 Not Found")

    @admin.command(name="test-not-found")
    def test_cmd() -> None:
        get_terraform_output("test_key")

    result = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-proj",
            "--instance-name",
            "mock-inst",
            "test-not-found",
        ],
    )
    assert result.exit_code != 0
    assert "Terraform state file not found" in result.output


@patch("google.cloud.storage.Client")
def test_get_terraform_output_from_gcs_forbidden(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client = MagicMock()
    mock_storage_client.return_value = mock_client
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_text.side_effect = Forbidden("403 Permission Denied")

    @admin.command(name="test-forbidden")
    def test_cmd() -> None:
        get_terraform_output("test_key")

    result = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-proj",
            "--instance-name",
            "mock-inst",
            "test-forbidden",
        ],
    )
    assert result.exit_code != 0
    assert "Permission denied accessing Terraform state" in result.output


@patch("google.cloud.storage.Client")
def test_get_terraform_output_from_gcs_invalid_json(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client = MagicMock()
    mock_storage_client.return_value = mock_client
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_text.return_value = "invalid-json"

    @admin.command(name="test-invalid-json")
    def test_cmd() -> None:
        get_terraform_output("test_key")

    result = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-proj",
            "--instance-name",
            "mock-inst",
            "test-invalid-json",
        ],
    )
    assert result.exit_code != 0
    assert "Failed to parse Terraform state" in result.output


@patch("google.cloud.storage.Client")
def test_get_terraform_output_from_gcs_missing_key(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client = MagicMock()
    mock_storage_client.return_value = mock_client
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_text.return_value = (
        '{"outputs": {"other_key": {"value": "abc"}}}'
    )

    @admin.command(name="test-missing-key")
    def test_cmd() -> None:
        get_terraform_output("test_key")

    result = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-proj",
            "--instance-name",
            "mock-inst",
            "test-missing-key",
        ],
    )
    assert result.exit_code != 0
    assert "Terraform output key 'test_key' not found" in result.output


def test_get_terraform_output_missing_paired_flags(runner: CliRunner) -> None:
    @admin.command(name="test-unpaired")
    def test_cmd() -> None:
        get_terraform_output("test_key")

    res1 = runner.invoke(admin, ["--project-id", "mock-proj", "test-unpaired"])
    assert res1.exit_code != 0
    assert (
        "Both --project-id and --instance-name must be specified together"
        in res1.output
    )

    res2 = runner.invoke(admin, ["--instance-name", "mock-inst", "test-unpaired"])
    assert res2.exit_code != 0
    assert (
        "Both --project-id and --instance-name must be specified together"
        in res2.output
    )


@patch("google.cloud.storage.Client")
def test_get_terraform_output_handles_falsy_values(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client = MagicMock()
    mock_storage_client.return_value = mock_client
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_text.return_value = """{
        "outputs": {
            "bool_key": {"value": false},
            "zero_key": {"value": 0}
        }
    }"""

    @admin.command(name="test-falsy")
    def test_cmd() -> None:
        v1 = get_terraform_output("bool_key")
        v2 = get_terraform_output("zero_key")
        click.echo(f"BOOL={v1} ZERO={v2}")

    result = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-proj",
            "--instance-name",
            "mock-inst",
            "test-falsy",
        ],
    )
    assert result.exit_code == 0
    assert "BOOL=False ZERO=0" in result.output


@patch("google.cloud.storage.Client")
def test_get_terraform_output_in_context_caching(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    """Verifies multiple get_terraform_output calls only download GCS blob once per command."""
    mock_client = MagicMock()
    mock_storage_client.return_value = mock_client
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_text.return_value = """{
        "outputs": {
            "project_id": {"value": "cached-proj"},
            "spanner_instance_id": {"value": "cached-spanner"}
        }
    }"""

    @admin.command(name="test-caching")
    def test_cmd() -> None:
        p_id = get_project_id()
        s_id = get_spanner_instance_id()
        click.echo(f"P={p_id} S={s_id}")

    result = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-proj",
            "--instance-name",
            "mock-inst",
            "test-caching",
        ],
    )
    assert result.exit_code == 0
    assert "P=cached-proj S=cached-spanner" in result.output
    # download_as_text must only be called ONCE despite 2 separate getter calls
    mock_blob.download_as_text.assert_called_once()
