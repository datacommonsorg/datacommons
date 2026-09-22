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
from datacommons_cli.client.sdmx_client import (
    SdmxAPIError,
    SdmxClient,
    SdmxClientError,
    build_query_params,
    parse_filters,
)

_CSV = "STRUCTURE,OBS_VALUE\ndataflow,100\n"
_AVAILABILITY = {"data": {"dataConstraints": [{"id": "DF_OBS_AVAILABILITY"}]}}

_ROOT_DATA_URL = "https://api.datacommons.org/sdmx/v3/data/dataflow/DC/DF_OBS/1.0.0/*"
_CORE_DATA_URL = (
    "https://dc-service-xyz.run.app/core/api/sdmx/v3/data/dataflow/DC/DF_OBS/1.0.0/*"
)


class TestParseFilters:
    def test_parses_key_value_pairs(self):
        assert parse_filters(["a=1", "b=2"]) == {"a": ["1"], "b": ["2"]}

    def test_groups_repeated_keys(self):
        assert parse_filters(["a=1", "a=2"]) == {"a": ["1", "2"]}

    def test_strips_surrounding_whitespace(self):
        assert parse_filters([" a = 1 "]) == {"a": ["1"]}

    def test_keeps_equals_signs_in_values(self):
        assert parse_filters(["a=x=y"]) == {"a": ["x=y"]}

    @pytest.mark.parametrize("bad", ["novalue", "=1", " =1"])
    def test_rejects_malformed_filters(self, bad):
        with pytest.raises(ValueError, match="Invalid filter"):
            parse_filters([bad])


class TestBuildQueryParams:
    def test_includes_the_variable(self):
        assert build_query_params("Count_Person") == {
            "c[variableMeasured]": "Count_Person"
        }

    def test_renders_constraints_as_component_params(self):
        params = build_query_params("V", {"observationAbout": "country/FRA"})

        assert params["c[observationAbout]"] == "country/FRA"

    def test_joins_multiple_values_with_commas(self):
        params = build_query_params("V", {"provenance": ["a", "b"]})

        assert params["c[provenance]"] == "a,b"


class TestSdmxClient:
    def test_get_data_returns_the_response_body(
        self, public_connection, make_response, make_session
    ):
        session = make_session(make_response(text=_CSV))
        client = SdmxClient(public_connection, session=session)

        assert client.get_data("Count_Person") == _CSV

    def test_get_data_sends_auth_headers_and_params(
        self, public_connection, make_response, make_session
    ):
        session = make_session(make_response(text=_CSV))

        SdmxClient(public_connection, session=session).get_data(
            "Count_Person", {"observationAbout": "country/USA"}
        )

        url, kwargs = session.get.call_args.args[0], session.get.call_args.kwargs
        assert url == _ROOT_DATA_URL
        assert kwargs["headers"]["X-API-Key"] == "test-key"
        assert kwargs["headers"]["X-Log-SDMX"] == "true"
        assert kwargs["headers"]["X-Use-Multi-Entity-Schema"] == "true"
        assert kwargs["params"]["c[observationAbout]"] == "country/USA"
        assert kwargs["params"]["format"] == "csv"

    def test_header_flags_can_be_disabled(
        self, public_connection, make_response, make_session
    ):
        session = make_session(make_response(text=_CSV))

        SdmxClient(public_connection, session=session).get_data(
            "V", log=False, multi_entity=False, accept="application/json"
        )

        headers = session.get.call_args.kwargs["headers"]
        assert headers["X-Log-SDMX"] == "false"
        assert headers["X-Use-Multi-Entity-Schema"] == "false"
        assert headers["Accept"] == "application/json"

    def test_get_availability_parses_json(
        self, public_connection, make_response, make_session
    ):
        session = make_session(
            make_response(json_body=_AVAILABILITY, content_type="application/json")
        )
        client = SdmxClient(public_connection, session=session)

        assert client.get_availability("provenance", "Count_Person") == _AVAILABILITY

    def test_get_availability_falls_back_to_raw_text(
        self, public_connection, make_response, make_session
    ):
        session = make_session(
            make_response(text="not json", content_type="text/plain")
        )
        client = SdmxClient(public_connection, session=session)

        assert client.get_availability("provenance", "V") == "not json"

    def test_instance_connection_prefers_the_core_api_root(
        self, instance_connection, make_response, make_session
    ):
        session = make_session(make_response(text=_CSV))

        SdmxClient(instance_connection, session=session).get_data("V")

        assert session.get.call_args.args[0] == _CORE_DATA_URL

    def test_a_404_retries_against_the_other_api_root(
        self, instance_connection, make_response, make_session
    ):
        session = make_session(make_response(404), make_response(text=_CSV))
        client = SdmxClient(instance_connection, session=session)

        assert client.get_data("V") == _CSV

        attempted = [call.args[0] for call in session.get.call_args_list]
        assert attempted == [
            _CORE_DATA_URL,
            "https://dc-service-xyz.run.app/sdmx/v3/data/dataflow/DC/DF_OBS/1.0.0/*",
        ]

    def test_the_discovered_api_root_is_reused(
        self, instance_connection, make_response, make_session
    ):
        session = make_session(
            make_response(404),
            make_response(text=_CSV),
            make_response(text=_CSV),
        )
        client = SdmxClient(instance_connection, session=session)

        client.get_data("V")
        client.get_data("V")

        # Only the first query pays for the discovery attempt.
        assert session.get.call_count == 3  # noqa: PLR2004

    def test_a_404_from_every_root_is_reported(
        self, public_connection, make_response, make_session
    ):
        session = make_session(
            make_response(404, reason="Not Found"), make_response(404)
        )
        client = SdmxClient(public_connection, session=session)

        with pytest.raises(SdmxAPIError) as excinfo:
            client.get_data("V")

        assert excinfo.value.status_code == 404  # noqa: PLR2004

    def test_api_errors_surface_the_server_message(
        self, public_connection, make_response, make_session
    ):
        session = make_session(
            make_response(401, json_body={"message": "API key not valid"})
        )
        client = SdmxClient(public_connection, session=session)

        with pytest.raises(SdmxAPIError, match="API key not valid") as excinfo:
            client.get_data("V")

        assert excinfo.value.status_code == 401  # noqa: PLR2004

    def test_api_errors_fall_back_to_the_reason_phrase(
        self, public_connection, make_response, make_session
    ):
        session = make_session(make_response(500, text="", reason="Server Error"))
        client = SdmxClient(public_connection, session=session)

        with pytest.raises(SdmxAPIError, match="Server Error"):
            client.get_data("V")

    def test_html_error_bodies_are_not_echoed(
        self, public_connection, make_response, make_session
    ):
        session = make_session(
            make_response(502, text="<html>gateway</html>", reason="Bad Gateway")
        )
        client = SdmxClient(public_connection, session=session)

        with pytest.raises(SdmxAPIError, match="Bad Gateway"):
            client.get_data("V")

    def test_network_failures_are_wrapped(
        self, public_connection, make_response, make_session
    ):
        session = make_session()
        session.get.side_effect = requests.ConnectionError("refused")
        client = SdmxClient(public_connection, session=session)

        with pytest.raises(SdmxClientError, match="Could not reach"):
            client.get_data("V")
