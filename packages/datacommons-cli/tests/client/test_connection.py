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

from unittest.mock import patch

import click
import pytest
from datacommons_cli.client.connection import (
    PUBLIC_API_URL,
    ApiLayout,
    ConnectionOptions,
    normalize_url,
    resolve_connection,
)

_TF_SERVICE_URL = "datacommons_cli.client.connection.get_datacommons_service_url"
_FETCH_ID_TOKEN = "datacommons_cli.client.connection.fetch_id_token"


class TestNormalizeUrl:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("api.datacommons.org", "https://api.datacommons.org"),
            ("https://api.datacommons.org", "https://api.datacommons.org"),
            ("https://api.datacommons.org/", "https://api.datacommons.org"),
            ("http://localhost:8080", "http://localhost:8080"),
            ("  api.datacommons.org  ", "https://api.datacommons.org"),
            ("dev.api.datacommons.org", "https://dev.api.datacommons.org"),
        ],
    )
    def test_normalizes_supported_forms(self, raw, expected):
        assert normalize_url(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "ftp://example.org", "https://"])
    def test_rejects_invalid_urls(self, raw):
        with pytest.raises(click.UsageError):
            normalize_url(raw)


class TestConnectionOptions:
    def test_url_cannot_be_combined_with_instance(self):
        with pytest.raises(click.UsageError, match="cannot be combined"):
            ConnectionOptions(
                url="api.datacommons.org", project_id="p", instance_name="i"
            )

    @pytest.mark.parametrize(
        ("project_id", "instance_name"),
        [("p", None), (None, "i")],
    )
    def test_instance_flags_are_required_together(self, project_id, instance_name):
        with pytest.raises(click.UsageError, match="must be provided together"):
            ConnectionOptions(project_id=project_id, instance_name=instance_name)

    def test_plain_url_is_valid(self):
        assert ConnectionOptions(url="localhost:8080").targets_instance is False


class TestResolveConnection:
    def test_defaults_to_the_public_api(self):
        connection = resolve_connection(ConnectionOptions())

        assert connection.base_url == PUBLIC_API_URL
        assert connection.preferred_layout == ApiLayout.ROOT
        assert connection.headers == {}

    def test_api_key_is_sent_as_a_header(self):
        connection = resolve_connection(ConnectionOptions(api_key="secret"))

        assert connection.headers == {"X-API-Key": "secret"}

    def test_url_overrides_the_default_endpoint(self):
        connection = resolve_connection(ConnectionOptions(url="localhost:8080"))

        assert connection.base_url == "https://localhost:8080"

    def test_instance_is_resolved_from_terraform_state_with_id_token(self):
        options = ConnectionOptions(project_id="my-proj", instance_name="prod")

        with (
            patch(_TF_SERVICE_URL, return_value="https://dc.run.app") as mock_lookup,
            patch(_FETCH_ID_TOKEN, return_value="id-token"),
        ):
            connection = resolve_connection(options)

        assert connection.base_url == "https://dc.run.app"
        assert connection.preferred_layout == ApiLayout.CORE_API
        assert connection.headers == {"Authorization": "Bearer id-token"}

        config = mock_lookup.call_args.args[0]
        assert (config.project_id, config.instance_name) == ("my-proj", "prod")
