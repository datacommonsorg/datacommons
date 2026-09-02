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
from datacommons_admin.core.utils.tf_utils import get_terraform_output
from google.cloud.exceptions import NotFound


@patch("google.cloud.storage.Client")
def test_get_terraform_output_from_gcs_canonical_success(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client_inst = MagicMock()
    mock_storage_client.return_value = mock_client_inst
    mock_bucket = MagicMock()
    mock_client_inst.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    state_content = """{
      "version": 4,
      "outputs": {
        "test_key": {
          "value": "gcs-resolved-val",
          "type": "string"
        }
      }
    }"""
    mock_blob.download_as_text.return_value = state_content

    @admin.command(name="test-get-output-canonical-success")
    def test_cmd() -> None:
        val = get_terraform_output("test_key")
        cached_val = get_terraform_output("test_key")
        click.echo(f"VAL={val} CACHED_VAL={cached_val}")

    result = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-project",
            "--instance-name",
            "mock-instance",
            "test-get-output-canonical-success",
        ],
    )
    assert result.exit_code == 0
    assert "VAL=gcs-resolved-val" in result.output
    mock_storage_client.assert_called_with(project="mock-project")
    mock_client_inst.bucket.assert_called_once_with(
        "tf-state-mock-instance-mock-project"
    )
    mock_bucket.blob.assert_called_once_with(
        "terraform/state/mock-instance/default.tfstate"
    )


@patch("google.cloud.storage.Client")
def test_get_terraform_output_from_gcs_location_success(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client_inst = MagicMock()
    mock_storage_client.return_value = mock_client_inst
    mock_bucket = MagicMock()
    mock_client_inst.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    state_content = """{
      "version": 4,
      "outputs": {
        "test_key": {
          "value": "gcs-resolved-val",
          "type": "string"
        }
      }
    }"""
    mock_blob.download_as_text.return_value = state_content

    @admin.command(name="test-get-output-location-success")
    def test_cmd() -> None:
        val = get_terraform_output("test_key")
        cached_val = get_terraform_output("test_key")
        click.echo(f"VAL={val} CACHED_VAL={cached_val}")

    result = runner.invoke(
        admin,
        [
            "--tf-state-location",
            "gs://custom-bucket/custom-prefix/state.tfstate",
            "test-get-output-location-success",
        ],
    )
    assert result.exit_code == 0
    assert "VAL=gcs-resolved-val" in result.output
    mock_storage_client.assert_called_once_with()
    mock_client_inst.bucket.assert_called_once_with("custom-bucket")
    mock_bucket.blob.assert_called_once_with("custom-prefix/state.tfstate")


def test_get_terraform_output_from_gcs_invalid_uri(runner: CliRunner) -> None:
    @admin.command(name="test-invalid-uri")
    def test_cmd() -> None:
        get_terraform_output("test_key")

    result = runner.invoke(
        admin,
        [
            "--tf-state-location",
            "https://not-gcs.com/state.tfstate",
            "test-invalid-uri",
        ],
    )
    assert result.exit_code != 0
    assert "Invalid GCS URI" in result.output


@patch("google.cloud.storage.Client")
def test_get_terraform_output_from_gcs_not_found(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client_inst = MagicMock()
    mock_storage_client.return_value = mock_client_inst
    mock_bucket = MagicMock()
    mock_client_inst.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_text.side_effect = NotFound("404 File Not Found")

    @admin.command(name="test-not-found")
    def test_cmd() -> None:
        get_terraform_output("test_key")

    result = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-project",
            "--instance-name",
            "mock-instance",
            "test-not-found",
        ],
    )
    assert result.exit_code != 0
    assert "Terraform state file not found" in result.output


@patch("google.cloud.storage.Client")
def test_get_terraform_output_from_gcs_invalid_json(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client_inst = MagicMock()
    mock_storage_client.return_value = mock_client_inst
    mock_bucket = MagicMock()
    mock_client_inst.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_blob.download_as_text.return_value = "invalid-json-content"

    @admin.command(name="test-invalid-json")
    def test_cmd() -> None:
        get_terraform_output("test_key")

    result = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-project",
            "--instance-name",
            "mock-instance",
            "test-invalid-json",
        ],
    )
    assert result.exit_code != 0
    assert "Failed to parse Terraform state" in result.output


@patch("google.cloud.storage.Client")
def test_get_terraform_output_from_gcs_missing_key(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client_inst = MagicMock()
    mock_storage_client.return_value = mock_client_inst
    mock_bucket = MagicMock()
    mock_client_inst.bucket.return_value = mock_bucket
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
            "mock-project",
            "--instance-name",
            "mock-instance",
            "test-missing-key",
        ],
    )
    assert result.exit_code != 0
    assert "Terraform output key 'test_key' not found" in result.output


def test_get_terraform_output_missing_project_or_instance_flag(
    runner: CliRunner,
) -> None:
    @admin.command(name="test-missing-pair")
    def test_cmd() -> None:
        get_terraform_output("test_key")

    # Only project-id without instance-name or tf-state-location
    res1 = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-project",
            "test-missing-pair",
        ],
    )
    assert res1.exit_code != 0
    assert (
        "Both --project-id and --instance-name must be specified together"
        in res1.output
    )

    # Only instance-name without project-id or tf-state-location
    res2 = runner.invoke(
        admin,
        [
            "--instance-name",
            "mock-instance",
            "test-missing-pair",
        ],
    )
    assert res2.exit_code != 0
    assert (
        "Both --project-id and --instance-name must be specified together"
        in res2.output
    )


def test_parse_gcs_uri_success() -> None:
    from datacommons_admin.core.utils.tf_utils import parse_gcs_uri

    bucket, blob = parse_gcs_uri("gs://my-bucket/path/to/default.tfstate")
    assert bucket == "my-bucket"
    assert blob == "path/to/default.tfstate"


def test_parse_gcs_uri_invalid_scheme() -> None:
    import pytest
    from datacommons_admin.core.utils.tf_utils import parse_gcs_uri

    with pytest.raises(click.ClickException, match="Must start with 'gs://'"):
        parse_gcs_uri("https://storage.googleapis.com/b/o")


def test_parse_gcs_uri_missing_bucket_or_blob() -> None:
    import pytest
    from datacommons_admin.core.utils.tf_utils import parse_gcs_uri

    with pytest.raises(
        click.ClickException, match="Must specify bucket and object path"
    ):
        parse_gcs_uri("gs://bucket-only")

    with pytest.raises(
        click.ClickException, match="Must specify bucket and object path"
    ):
        parse_gcs_uri("gs:///blob-only")


def test_parse_terraform_state_outputs_success() -> None:
    from datacommons_admin.core.utils.tf_utils import parse_terraform_state_outputs

    raw_json = '{"outputs": {"k1": {"value": "v1"}, "bool_k": {"value": false}, "int_k": {"value": 0}}}'
    outputs = parse_terraform_state_outputs(raw_json, "test-source")
    assert outputs["k1"]["value"] == "v1"
    assert outputs["bool_k"]["value"] is False
    assert outputs["int_k"]["value"] == 0


def test_parse_terraform_state_outputs_errors() -> None:
    import pytest
    from datacommons_admin.core.utils.tf_utils import parse_terraform_state_outputs

    with pytest.raises(
        click.ClickException, match="Failed to parse Terraform state.*as valid JSON"
    ):
        parse_terraform_state_outputs("invalid-json", "test-source")

    with pytest.raises(click.ClickException, match="Expected a JSON object"):
        parse_terraform_state_outputs('["not", "a", "dict"]', "test-source")

    with pytest.raises(click.ClickException, match="No outputs found"):
        parse_terraform_state_outputs('{"outputs": {}}', "test-source")


def test_terraform_state_config() -> None:
    from datacommons_admin.core.utils.models import TerraformStateConfig

    # Local mode
    local_cfg = TerraformStateConfig()
    assert not local_cfg.is_remote

    # Explicit URI mode
    uri_cfg = TerraformStateConfig(
        tf_state_location="gs://custom-b/custom-p/custom.tfstate"
    )
    assert uri_cfg.is_remote
    assert uri_cfg.gcs_uri == "gs://custom-b/custom-p/custom.tfstate"

    # Explicit locations are exact object URIs, regardless of file extension.
    exact_cfg = TerraformStateConfig(tf_state_location="gs://custom-b/custom-state")
    assert exact_cfg.gcs_uri == "gs://custom-b/custom-state"

    # Canonical project-id + instance-name mode
    canonical_cfg = TerraformStateConfig(project_id="my-proj", instance_name="my-inst")
    assert canonical_cfg.is_remote
    assert (
        canonical_cfg.gcs_uri
        == "gs://tf-state-my-inst-my-proj/terraform/state/my-inst/default.tfstate"
    )


@patch("google.cloud.storage.Client")
def test_get_terraform_output_handles_falsy_values(
    mock_storage_client: MagicMock, runner: CliRunner
) -> None:
    mock_client_inst = MagicMock()
    mock_storage_client.return_value = mock_client_inst
    mock_bucket = MagicMock()
    mock_client_inst.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    state_content = """{
      "version": 4,
      "outputs": {
        "bool_key": {"value": false},
        "zero_key": {"value": 0}
      }
    }"""
    mock_blob.download_as_text.return_value = state_content

    @admin.command(name="test-falsy-outputs")
    def test_cmd() -> None:
        val1 = get_terraform_output("bool_key")
        val2 = get_terraform_output("zero_key")
        click.echo(f"BOOL={val1} ZERO={val2}")

    result = runner.invoke(
        admin,
        [
            "--project-id",
            "mock-project",
            "--instance-name",
            "mock-instance",
            "test-falsy-outputs",
        ],
    )
    assert result.exit_code == 0
    assert "BOOL=False ZERO=0" in result.output
