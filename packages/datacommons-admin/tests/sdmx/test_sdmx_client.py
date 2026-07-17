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

import pytest
import requests
from datacommons_admin.core.clients import (
    SdmxAPIError,
    SdmxAuthError,
    SdmxClient,
    SdmxClientError,
)


def test_sdmx_client_init_localhost() -> None:
    client = SdmxClient("http://localhost:8080")
    assert isinstance(client.session, requests.Session)
    assert "Authorization" not in client.session.headers


def test_sdmx_client_init_user_credentials() -> None:
    mock_creds = MagicMock()
    mock_creds.id_token = "mock-user-token"

    with patch("google.auth.default", return_value=(mock_creds, "mock-project")):
        client = SdmxClient("https://service.run.app")
        assert client.session.headers["Authorization"] == "Bearer mock-user-token"


def test_sdmx_client_init_service_account_fallback() -> None:
    mock_creds = MagicMock(spec=[])  # no id_token attribute

    with (
        patch("google.auth.default", return_value=(mock_creds, "mock-project")),
        patch(
            "google.oauth2.id_token.fetch_id_token",
            return_value="mock-sa-token",
        ) as mock_fetch,
    ):
        client = SdmxClient("https://service.run.app")
        assert client.session.headers["Authorization"] == "Bearer mock-sa-token"
        mock_fetch.assert_called_once()


def test_sdmx_client_init_auth_failure() -> None:
    with patch(
        "google.auth.default",
        side_effect=Exception("No credentials available"),
    ), pytest.raises(SdmxAuthError, match="Failed to authenticate"):
        SdmxClient("https://service.run.app")


def test_sdmx_client_parse_filter_strings() -> None:
    filters = ["donorPlace=country/FRA", "donorPlace=country/USA", "unit=USD"]
    parsed = SdmxClient.parse_filter_strings(filters)
    assert parsed == {
        "donorPlace": ["country/FRA", "country/USA"],
        "unit": ["USD"],
    }


def test_sdmx_client_parse_filter_strings_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid filter format"):
        SdmxClient.parse_filter_strings(["invalid_without_equals"])


def test_sdmx_client_build_query_params() -> None:
    params = SdmxClient.build_query_params(
        variable="HealthAidFunding",
        constraints={
            "donorPlace": ["country/FRA", "country/USA"],
            "unit": "USD",
        },
        extra_params={"format": "csv"},
    )
    assert params == {
        "c[variableMeasured]": "HealthAidFunding",
        "c[donorPlace]": "country/FRA,country/USA",
        "c[unit]": "USD",
        "format": "csv",
    }


def test_sdmx_client_get_data_success() -> None:
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.text = "STRUCTURE,STRUCTURE_ID\ndataflow,DC:DF_OBS"
    mock_session.get.return_value = mock_resp

    client = SdmxClient("https://mock-service", session=mock_session)
    csv_data = client.get_data(
        variable="HealthAidFunding",
        constraints={"donorPlace": "country/FRA"},
    )

    assert csv_data == "STRUCTURE,STRUCTURE_ID\ndataflow,DC:DF_OBS"
    mock_session.get.assert_called_once_with(
        "https://mock-service/core/api/sdmx/v3/data/dataflow/DC/DF_OBS/1.0.0/*",
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


def test_sdmx_client_get_availability_json() -> None:
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.json.return_value = {"meta": {"id": "DF_OBS_AVAILABILITY"}}
    mock_session.get.return_value = mock_resp

    client = SdmxClient("https://mock-service", session=mock_session)
    result = client.get_availability(
        component_id="donorPlace",
        variable="HealthAidFunding",
        log=False,
        multi_entity=False,
    )

    assert isinstance(result, dict)
    assert result["meta"]["id"] == "DF_OBS_AVAILABILITY"
    mock_session.get.assert_called_once_with(
        "https://mock-service/core/api/sdmx/v3/availability/dataflow/DC/DF_OBS/1.0.0/*/donorPlace",
        params={"c[variableMeasured]": "HealthAidFunding"},
        headers={
            "X-Use-Multi-Entity-Schema": "false",
            "X-Log-SDMX": "false",
        },
        timeout=60,
    )


def test_sdmx_client_api_error() -> None:
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"message": "unsupported component"}
    mock_session.get.return_value = mock_resp

    client = SdmxClient("https://mock-service", session=mock_session)
    with pytest.raises(SdmxAPIError) as exc_info:
        client.get_availability("bad_comp", "Var")

    assert exc_info.value.status_code == 400
    assert "unsupported component" in exc_info.value.message


def test_sdmx_client_network_error() -> None:
    mock_session = MagicMock()
    mock_session.get.side_effect = requests.RequestException("Connection refused")

    client = SdmxClient("https://mock-service", session=mock_session)
    with pytest.raises(SdmxClientError, match="Network error connecting"):
        client.get_data("Var")
