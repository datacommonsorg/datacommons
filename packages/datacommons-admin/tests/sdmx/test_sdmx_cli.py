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
from unittest.mock import MagicMock, patch

import pytest
import requests
from click.testing import CliRunner
from datacommons_admin.admin_cli import admin
from datacommons_admin.core.clients import SdmxClient


@pytest.fixture
def mock_sdmx_session():
    """Mocks _get_client to return an SdmxClient with a mock requests.Session."""
    session = MagicMock()
    client = SdmxClient("https://mock-dc-service", session=session)
    with patch("datacommons_admin.sdmx.sdmx_cli._get_client", return_value=client):
        yield session


@pytest.mark.usefixtures("mock_terraform_sdmx")
def test_sdmx_data_success(
    mock_sdmx_session: MagicMock, runner: CliRunner
) -> None:
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.text = "STRUCTURE,STRUCTURE_ID,ACTION\ndataflow,DC:DF_OBS,I"
    mock_resp.headers = {"Content-Type": "application/vnd.sdmx.data+csv"}
    mock_sdmx_session.get.return_value = mock_resp

    result = runner.invoke(
        admin,
        [
            "sdmx",
            "data",
            "-v",
            "HealthAidFunding",
            "-f",
            "donorPlace=country/FRA",
        ],
    )
    assert result.exit_code == 0
    assert "STRUCTURE,STRUCTURE_ID,ACTION" in result.output
    mock_sdmx_session.get.assert_called_once_with(
        "https://mock-dc-service/core/api/sdmx/v3/data/dataflow/DC/DF_OBS/1.0.0/*",
        params={
            "c[variableMeasured]": "HealthAidFunding",
            "c[donorPlace]": "country/FRA",
            "format": "csv",
        },
        headers={
            "X-Use-Multi-Entity-Schema": "true",
            "X-Log-SDMX": "true",
        },
        timeout=60,
    )


@pytest.mark.usefixtures("mock_terraform_sdmx")
def test_sdmx_data_output_file(
    mock_sdmx_session: MagicMock, runner: CliRunner, tmp_path: Path
) -> None:
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.text = "COL1,COL2\nval1,val2"
    mock_resp.headers = {"Content-Type": "application/vnd.sdmx.data+csv"}
    mock_sdmx_session.get.return_value = mock_resp

    out_file = tmp_path / "out.csv"
    result = runner.invoke(
        admin,
        [
            "sdmx",
            "data",
            "-v",
            "HealthAidFunding",
            "-o",
            str(out_file),
        ],
    )
    assert result.exit_code == 0
    assert out_file.read_text(encoding="utf-8") == "COL1,COL2\nval1,val2"


def test_sdmx_data_missing_variable(runner: CliRunner) -> None:
    result = runner.invoke(admin, ["sdmx", "data"])
    assert result.exit_code != 0
    assert "Missing option '--variable'" in result.output


def test_sdmx_data_invalid_filter_format(runner: CliRunner) -> None:
    result = runner.invoke(
        admin,
        ["sdmx", "data", "-v", "Var", "-f", "invalid_filter_format"],
    )
    assert result.exit_code != 0
    assert "Invalid filter format" in result.output


@pytest.mark.usefixtures("mock_terraform_sdmx")
def test_sdmx_availability_success(
    mock_sdmx_session: MagicMock, runner: CliRunner
) -> None:
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.text = '{"meta": {"id": "DF_OBS_AVAILABILITY"}}'
    mock_resp.json.return_value = {"meta": {"id": "DF_OBS_AVAILABILITY"}}
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_sdmx_session.get.return_value = mock_resp

    result = runner.invoke(
        admin,
        [
            "sdmx",
            "availability",
            "donorPlace",
            "-v",
            "HealthAidFunding",
            "--no-log",
            "--no-multi-entity",
        ],
    )
    assert result.exit_code == 0
    assert "DF_OBS_AVAILABILITY" in result.output
    mock_sdmx_session.get.assert_called_once_with(
        "https://mock-dc-service/core/api/sdmx/v3/availability/dataflow/DC/DF_OBS/1.0.0/*/donorPlace",
        params={"c[variableMeasured]": "HealthAidFunding"},
        headers={
            "X-Use-Multi-Entity-Schema": "false",
            "X-Log-SDMX": "false",
        },
        timeout=60,
    )


@pytest.mark.usefixtures("mock_terraform_sdmx")
def test_sdmx_api_error_handling(
    mock_sdmx_session: MagicMock, runner: CliRunner
) -> None:
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"message": "unsupported SDMX component"}
    mock_sdmx_session.get.return_value = mock_resp

    result = runner.invoke(
        admin,
        ["sdmx", "availability", "invalidComp", "-v", "Var"],
    )
    assert result.exit_code != 0
    assert (
        "SDMX API returned HTTP 400: unsupported SDMX component"
        in result.output
    )


@pytest.mark.usefixtures("mock_terraform_sdmx")
def test_sdmx_network_error(
    mock_sdmx_session: MagicMock, runner: CliRunner
) -> None:
    mock_sdmx_session.get.side_effect = requests.RequestException(
        "Connection refused"
    )

    result = runner.invoke(
        admin,
        ["sdmx", "data", "-v", "Var"],
    )
    assert result.exit_code != 0
    assert "Network error connecting to Data Commons service" in result.output
