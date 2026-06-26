# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for CentralAPIClient."""

from unittest.mock import patch, MagicMock
import pytest
import requests

from datacommons_api.core.exceptions import (
    APIKeyUnauthorizedError,
    APIKeyForbiddenError,
)
from datacommons_api.services.central_api_client import CentralAPIClient


def test_query_success():
    client = CentralAPIClient(api_key="valid-key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "success"}

    with patch("requests.Session.post", return_value=mock_response) as mock_post:
        result = client.query_usa_population()

        assert result == {"data": "success"}
        mock_post.assert_called_once()
        # Verify headers have the key
        called_headers = mock_post.call_args[1].get("headers", {})
        assert called_headers.get("X-Goog-Api-Key") == "valid-key"


def test_query_unauthorized():
    client = CentralAPIClient(api_key="invalid-key")

    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("requests.Session.post", return_value=mock_response):
        with pytest.raises(APIKeyUnauthorizedError) as exc_info:
            client.query_usa_population()
        assert "Invalid or expired API key" in str(exc_info.value)


def test_query_forbidden():
    client = CentralAPIClient(api_key="forbidden-key")

    mock_response = MagicMock()
    mock_response.status_code = 403

    with patch("requests.Session.post", return_value=mock_response):
        with pytest.raises(APIKeyForbiddenError) as exc_info:
            client.query_usa_population()
        assert "API key lacks permissions" in str(exc_info.value)


def test_query_timeout_propagates():
    client = CentralAPIClient(api_key="valid-key")

    with patch(
        "requests.Session.post",
        side_effect=requests.exceptions.Timeout("Connection timed out"),
    ):
        with pytest.raises(requests.exceptions.Timeout) as exc_info:
            client.query_usa_population()
        assert "Connection timed out" in str(exc_info.value)
