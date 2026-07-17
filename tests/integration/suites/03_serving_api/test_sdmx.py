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

import pytest
import requests
from datacommons_admin.core.clients import SdmxClient

from tests.integration.core.cli_runner import DatacommonsCLI
from tests.integration.core.config_schema import (
    SDMXAvailabilityQuerySpec,
    SDMXDataQuerySpec,
)


class TestSDMXAPI:
    """Validates SDMX 3.0 standard statistical Data and Availability APIs via HTTP and SdmxClient."""

    def test_sdmx_data_query(
        self,
        seeded_testbed,
        dcp_target,
        auth_headers,
        sdmx_data_spec: SDMXDataQuerySpec | None,
    ):
        """Tests SDMX 3.0 Data API (/sdmx/v3/data) with dimension constraints via direct HTTP."""
        if not sdmx_data_spec:
            pytest.skip(
                "SDMX stage disabled or no SDMX data queries defined in manifest."
            )

        headers = dict(auth_headers)
        headers["X-Log-SDMX"] = "true"
        headers["X-Use-Multi-Entity-Schema"] = "true"

        url = f"{dcp_target.serving_url}/core/api/sdmx/v3/data/dataflow/{sdmx_data_spec.dataflow}"
        params = {"format": sdmx_data_spec.format}
        for k, v in sdmx_data_spec.constraints.items():
            params[f"c[{k}]"] = v

        res = requests.get(url, params=params, headers=headers, timeout=30)
        assert res.status_code == 200, (
            f"SDMX 3.0 Data API returned {res.status_code}: {res.text}"
        )

        for expected in sdmx_data_spec.expected_csv_contains:
            assert expected in res.text, (
                f"Expected '{expected}' in SDMX response: {res.text[:300]}"
            )

    def test_sdmx_availability_query(
        self,
        seeded_testbed,
        dcp_target,
        auth_headers,
        sdmx_avail_spec: SDMXAvailabilityQuerySpec | None,
    ):
        """Tests SDMX 3.0 Availability API (/sdmx/v3/availability) with dimension constraints via direct HTTP."""
        if not sdmx_avail_spec:
            pytest.skip(
                "SDMX stage disabled or no SDMX availability queries defined in manifest."
            )

        headers = dict(auth_headers)
        headers["X-Log-SDMX"] = "true"
        headers["X-Use-Multi-Entity-Schema"] = "true"

        url = f"{dcp_target.serving_url}/core/api/sdmx/v3/availability/dataflow/{sdmx_avail_spec.dataflow}"
        params = {}
        for k, v in sdmx_avail_spec.constraints.items():
            params[f"c[{k}]"] = v

        res = requests.get(url, params=params, headers=headers, timeout=30)
        assert res.status_code == 200, (
            f"SDMX 3.0 Availability API returned {res.status_code}: {res.text}"
        )

        if sdmx_avail_spec.expected_provenance:
            assert sdmx_avail_spec.expected_provenance in res.text, (
                f"Expected provenance '{sdmx_avail_spec.expected_provenance}' in response: {res.text[:300]}"
            )

    def test_sdmx_client_data_query(
        self,
        seeded_testbed,
        dcp_target,
        sdmx_data_spec: SDMXDataQuerySpec | None,
    ):
        """Validates SdmxClient.get_data programmatic access against live endpoints."""
        if not sdmx_data_spec:
            pytest.skip(
                "SDMX stage disabled or no SDMX data queries defined in manifest."
            )

        var = sdmx_data_spec.constraints.get("variableMeasured", "")
        if not var:
            pytest.skip("No variableMeasured constraint defined.")

        other_constraints = {
            k: v
            for k, v in sdmx_data_spec.constraints.items()
            if k != "variableMeasured"
        }

        client = SdmxClient(base_url=dcp_target.serving_url)
        csv_text = client.get_data(
            variable=var,
            constraints=other_constraints,
            response_format=sdmx_data_spec.format or "csv",
        )

        for expected in sdmx_data_spec.expected_csv_contains:
            assert expected in csv_text, (
                f"Expected '{expected}' in SdmxClient get_data response: {csv_text[:300]}"
            )

    def test_sdmx_client_availability_query(
        self,
        seeded_testbed,
        dcp_target,
        sdmx_avail_spec: SDMXAvailabilityQuerySpec | None,
    ):
        """Validates SdmxClient.get_availability programmatic access against live endpoints."""
        if not sdmx_avail_spec:
            pytest.skip(
                "SDMX stage disabled or no SDMX availability queries defined in manifest."
            )

        var = sdmx_avail_spec.constraints.get("variableMeasured", "")
        if not var:
            pytest.skip("No variableMeasured constraint defined.")

        parts = sdmx_avail_spec.dataflow.rstrip("/").split("/")
        component_id = parts[-1] if parts else "provenance"

        other_constraints = {
            k: v
            for k, v in sdmx_avail_spec.constraints.items()
            if k != "variableMeasured"
        }

        client = SdmxClient(base_url=dcp_target.serving_url)
        result = client.get_availability(
            component_id=component_id,
            variable=var,
            constraints=other_constraints,
        )

        result_str = str(result)
        if sdmx_avail_spec.expected_provenance:
            assert sdmx_avail_spec.expected_provenance in result_str, (
                f"Expected provenance '{sdmx_avail_spec.expected_provenance}' in SdmxClient availability: {result_str[:300]}"
            )


@pytest.mark.cloud_only
class TestSDMXCLI:
    """Validates Data Commons CLI SDMX commands against live target testbed."""

    def test_sdmx_cli_data_query(
        self,
        seeded_testbed,
        dcp_cli: DatacommonsCLI,
        sdmx_data_spec: SDMXDataQuerySpec | None,
    ):
        """Validates 'datacommons admin sdmx data' returns live observations."""
        if not sdmx_data_spec:
            pytest.skip("SDMX data query spec not defined.")

        var = sdmx_data_spec.constraints.get("variableMeasured", "")
        if not var:
            pytest.skip("No variableMeasured constraint defined.")

        cli_args = ["admin", "sdmx", "data", "-v", var]
        for k, v in sdmx_data_spec.constraints.items():
            if k == "variableMeasured":
                continue
            cli_args.extend(["-f", f"{k}={v}"])

        res = dcp_cli.run(cli_args)
        assert res.exit_code == 0, f"SDMX CLI data query failed: {res.output}"

        for expected in sdmx_data_spec.expected_csv_contains:
            assert expected in res.stdout, (
                f"Expected '{expected}' in SDMX CLI data stdout: {res.stdout[:300]}"
            )

    def test_sdmx_cli_data_output_file(
        self,
        seeded_testbed,
        dcp_cli: DatacommonsCLI,
        sdmx_data_spec: SDMXDataQuerySpec | None,
        tmp_path: Path,
    ):
        """Validates 'datacommons admin sdmx data -o <file>' writes observations to file."""
        if not sdmx_data_spec:
            pytest.skip("SDMX data query spec not defined.")

        var = sdmx_data_spec.constraints.get("variableMeasured", "")
        if not var:
            pytest.skip("No variableMeasured constraint defined.")

        out_file = tmp_path / "live_observations.csv"
        cli_args = ["admin", "sdmx", "data", "-v", var, "-o", str(out_file)]
        for k, v in sdmx_data_spec.constraints.items():
            if k == "variableMeasured":
                continue
            cli_args.extend(["-f", f"{k}={v}"])

        res = dcp_cli.run(cli_args)
        assert res.exit_code == 0, f"SDMX CLI data query with -o failed: {res.output}"
        assert out_file.exists(), f"Output file '{out_file}' was not created."

        file_content = out_file.read_text(encoding="utf-8")
        for expected in sdmx_data_spec.expected_csv_contains:
            assert expected in file_content, (
                f"Expected '{expected}' in output file content: {file_content[:300]}"
            )

    def test_sdmx_cli_availability_query(
        self,
        seeded_testbed,
        dcp_cli: DatacommonsCLI,
        sdmx_avail_spec: SDMXAvailabilityQuerySpec | None,
    ):
        """Validates 'datacommons admin sdmx availability' returns live dimension values."""
        if not sdmx_avail_spec:
            pytest.skip("SDMX availability query spec not defined.")

        var = sdmx_avail_spec.constraints.get("variableMeasured", "")
        if not var:
            pytest.skip("No variableMeasured constraint defined.")

        parts = sdmx_avail_spec.dataflow.rstrip("/").split("/")
        component_id = parts[-1] if parts else "provenance"

        cli_args = ["admin", "sdmx", "availability", component_id, "-v", var]
        for k, v in sdmx_avail_spec.constraints.items():
            if k == "variableMeasured":
                continue
            cli_args.extend(["-f", f"{k}={v}"])

        res = dcp_cli.run(cli_args)
        assert res.exit_code == 0, f"SDMX CLI availability query failed: {res.output}"

        if sdmx_avail_spec.expected_provenance:
            assert sdmx_avail_spec.expected_provenance in res.stdout, (
                f"Expected provenance '{sdmx_avail_spec.expected_provenance}' in SDMX CLI availability stdout: {res.stdout[:300]}"
            )
