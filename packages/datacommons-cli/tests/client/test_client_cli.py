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

import json
from unittest.mock import patch

import pytest
from datacommons_cli.cli import cli
from datacommons_cli.client.sdmx_client import SdmxAPIError

_CSV = "STRUCTURE,OBS_VALUE\ndataflow,100\n"
_AVAILABILITY = {"data": {"dataConstraints": [{"id": "DF_OBS_AVAILABILITY"}]}}

_GET_DATA = "datacommons_cli.client.client_cli.SdmxClient.get_data"
_GET_AVAILABILITY = "datacommons_cli.client.client_cli.SdmxClient.get_availability"


@pytest.fixture
def get_data():
    """Patches SdmxClient.get_data, returning a small CSV payload."""
    with patch(_GET_DATA, return_value=_CSV) as mock:
        yield mock


@pytest.fixture
def get_availability():
    """Patches SdmxClient.get_availability, returning an SDMX-JSON structure."""
    with patch(_GET_AVAILABILITY, return_value=_AVAILABILITY) as mock:
        yield mock


class TestSdmxDataCommand:
    def test_writes_observations_to_stdout(self, runner, get_data):
        result = runner.invoke(
            cli, ["client", "--api-key", "k", "sdmx-data", "-v", "Count_Person"]
        )

        assert result.exit_code == 0, result.output
        assert _CSV in result.stdout

    def test_passes_filters_as_constraints(self, runner, get_data):
        result = runner.invoke(
            cli,
            [
                "client",
                "--api-key",
                "k",
                "sdmx-data",
                "-v",
                "V",
                "-f",
                "observationAbout=country/FRA",
                "-f",
                "provenance=a",
            ],
        )

        assert result.exit_code == 0, result.output
        assert get_data.call_args.args[1] == {
            "observationAbout": ["country/FRA"],
            "provenance": ["a"],
        }

    def test_writes_to_an_output_file(self, runner, get_data, tmp_path):
        out_file = tmp_path / "nested" / "obs.csv"

        result = runner.invoke(
            cli,
            ["client", "--api-key", "k", "sdmx-data", "-v", "V", "-o", str(out_file)],
        )

        assert result.exit_code == 0, result.output
        assert out_file.read_text(encoding="utf-8") == _CSV
        assert _CSV not in result.stdout

    def test_forwards_header_flags(self, runner, get_data):
        result = runner.invoke(
            cli,
            [
                "client",
                "--api-key",
                "k",
                "sdmx-data",
                "-v",
                "V",
                "--no-log",
                "--no-multi-entity",
            ],
        )

        assert result.exit_code == 0, result.output
        assert get_data.call_args.kwargs["log"] is False
        assert get_data.call_args.kwargs["multi_entity"] is False

    def test_rejects_malformed_filters(self, runner):
        result = runner.invoke(
            cli, ["client", "--api-key", "k", "sdmx-data", "-v", "V", "-f", "bad"]
        )

        assert result.exit_code != 0
        assert "Invalid filter" in result.output

    def test_requires_a_variable(self, runner):
        result = runner.invoke(cli, ["client", "sdmx-data"])

        assert result.exit_code != 0
        assert "--variable" in result.output


class TestSdmxAvailabilityCommand:
    def test_pretty_prints_the_structure(self, runner, get_availability):
        result = runner.invoke(
            cli,
            ["client", "--api-key", "k", "sdmx-availability", "provenance", "-v", "V"],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == _AVAILABILITY

    def test_passes_the_component_id(self, runner, get_availability):
        result = runner.invoke(
            cli, ["client", "--api-key", "k", "sdmx-availability", "unit", "-v", "V"]
        )

        assert result.exit_code == 0, result.output
        assert get_availability.call_args.args[0] == "unit"

    def test_requires_a_component_id(self, runner):
        result = runner.invoke(cli, ["client", "sdmx-availability", "-v", "V"])

        assert result.exit_code != 0


class TestEndpointTargeting:
    def test_defaults_to_the_public_api(self, runner, get_data):
        result = runner.invoke(
            cli, ["client", "--api-key", "k", "sdmx-data", "-v", "V"]
        )

        assert result.exit_code == 0, result.output
        assert "Querying https://api.datacommons.org" in result.stderr

    def test_reads_the_api_key_from_the_environment(self, runner, get_data):
        result = runner.invoke(
            cli,
            ["client", "sdmx-data", "-v", "V"],
            env={"DATACOMMONS_API_KEY": "from-env"},
        )

        assert result.exit_code == 0, result.output

    def test_url_selects_another_endpoint(self, runner, get_data):
        result = runner.invoke(
            cli,
            ["client", "--url", "localhost:8080", "sdmx-data", "-v", "V"],
        )

        assert result.exit_code == 0, result.output
        assert "Querying https://localhost:8080" in result.stderr

    def test_url_conflicts_with_instance_selection(self, runner):
        result = runner.invoke(
            cli,
            [
                "client",
                "--url",
                "api.datacommons.org",
                "--project-id",
                "p",
                "--instance-name",
                "i",
                "sdmx-data",
                "-v",
                "V",
            ],
        )

        assert result.exit_code != 0
        assert "cannot be combined" in result.output

    def test_instance_is_resolved_from_terraform_state(self, runner, get_data):
        with (
            patch(
                "datacommons_cli.client.connection.get_datacommons_service_url",
                return_value="https://dc.run.app",
            ),
            patch(
                "datacommons_cli.client.connection.fetch_id_token",
                return_value="token",
            ),
        ):
            result = runner.invoke(
                cli,
                [
                    "client",
                    "--project-id",
                    "p",
                    "--instance-name",
                    "prod",
                    "sdmx-data",
                    "-v",
                    "V",
                ],
            )

        assert result.exit_code == 0, result.output
        assert "Resolving instance 'prod'" in result.stderr
        assert "Querying https://dc.run.app" in result.stderr


class TestErrorReporting:
    def test_auth_failures_include_api_key_guidance(self, runner):
        with patch(_GET_DATA, side_effect=SdmxAPIError(401, "unauthenticated")):
            result = runner.invoke(cli, ["client", "sdmx-data", "-v", "V"])

        assert result.exit_code != 0
        assert "DATACOMMONS_API_KEY" in result.output
        assert "--project-id" in result.output

    def test_other_api_errors_are_reported_verbatim(self, runner):
        with patch(_GET_DATA, side_effect=SdmxAPIError(400, "bad request")):
            result = runner.invoke(
                cli, ["client", "--api-key", "k", "sdmx-data", "-v", "V"]
            )

        assert result.exit_code != 0
        assert "bad request" in result.output
        assert "DATACOMMONS_API_KEY" not in result.output
