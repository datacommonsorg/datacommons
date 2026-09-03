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


import pytest
import requests

from tests.integration.core.config_schema import (
    SDMXAvailabilityQuerySpec,
    SDMXDataQuerySpec,
)


class TestSDMXAPI:
    """Validates SDMX 3.0 standard statistical Data and Availability APIs.

    Exercises statistical variable data retrieval and dimension facet discovery
    across local and federated BaseDC properties, testing both happy paths (HTTP 200)
    and negative constraint mismatches (HTTP 400).
    """

    def test_sdmx_data_query(
        self,
        seeded_testbed,
        dcp_target,
        auth_headers,
        sdmx_data_spec: SDMXDataQuerySpec | None,
    ):
        """Tests SDMX 3.0 Data API (/sdmx/v3/data) with dimension constraints.

        Validates:
          1. Response status code matches expected_status (200 for data, 400 for negative tests).
          2. Error response contains expected_error_contains when validating error handling.
          3. CSV payload contains expected strings (dimensions, entities, observation values).
        """
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
        assert res.status_code == sdmx_data_spec.expected_status, (
            f"SDMX 3.0 Data API returned {res.status_code} (expected {sdmx_data_spec.expected_status}): {res.text[:300]}"
        )

        if sdmx_data_spec.expected_error_contains:
            assert sdmx_data_spec.expected_error_contains in res.text, (
                f"Expected error '{sdmx_data_spec.expected_error_contains}' in response: {res.text[:300]}"
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
        """Tests SDMX 3.0 Availability API (/sdmx/v3/availability) with dimension constraints.

        Validates:
          1. Status code matches expected_status (200).
          2. Provenance ID matches expected_provenance if specified.
          3. Dimension component values in expected_values_contain (e.g. ['Female', 'Male'])
             appear in the returned dimension availability structure.
        """
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
        assert res.status_code == sdmx_avail_spec.expected_status, (
            f"SDMX 3.0 Availability API returned {res.status_code} (expected {sdmx_avail_spec.expected_status}): {res.text[:300]}"
        )

        if sdmx_avail_spec.expected_error_contains:
            assert sdmx_avail_spec.expected_error_contains in res.text, (
                f"Expected error '{sdmx_avail_spec.expected_error_contains}' in response: {res.text[:300]}"
            )

        if sdmx_avail_spec.expected_provenance:
            assert sdmx_avail_spec.expected_provenance in res.text, (
                f"Expected provenance '{sdmx_avail_spec.expected_provenance}' in response: {res.text[:300]}"
            )

        for expected in sdmx_avail_spec.expected_values_contain:
            assert expected in res.text, (
                f"Expected dimension value '{expected}' in availability response: {res.text[:300]}"
            )
