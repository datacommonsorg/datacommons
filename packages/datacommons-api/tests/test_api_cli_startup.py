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

"""Tests for CLI startup validation hook."""

import os
import sys
from unittest.mock import patch, MagicMock
import pytest

from datacommons_api.core.exceptions import (
    APIKeyUnauthorizedError,
    APIKeyForbiddenError,
)
from datacommons_api.api_cli import validate_api_key_startup


@pytest.fixture(autouse=True)
def clean_env():
    """Ensure a clean environment for each test and restore it afterwards."""
    old_env = dict(os.environ)
    # Clear key environment variables
    os.environ.pop("DC_API_KEY", None)
    os.environ.pop("DC_API_KEY_OPTIONAL", None)
    os.environ.pop("DC_API_KEY_STRICT_VALIDATION", None)
    os.environ.pop("_DC_API_KEY_STARTUP_DEGRADED", None)
    os.environ.pop("_DC_API_KEY_STATUS", None)
    yield
    os.environ.clear()
    os.environ.update(old_env)


def test_startup_success():
    os.environ["DC_API_KEY"] = "valid-key"

    with (
        patch(
            "datacommons_api.services.central_api_client.CentralAPIClient.query_usa_population"
        ) as mock_query,
        patch("sys.exit") as mock_exit,
    ):
        validate_api_key_startup()

        mock_query.assert_called_once()
        mock_exit.assert_not_called()
        assert os.environ.get("_DC_API_KEY_STARTUP_DEGRADED") == "false"
        assert os.environ.get("_DC_API_KEY_STATUS") == "verified"


def test_startup_missing_key_fails():
    with (
        patch("sys.exit", side_effect=SystemExit) as mock_exit,
        patch("sys.stderr.write") as mock_stderr,
    ):
        with pytest.raises(SystemExit):
            validate_api_key_startup()

        mock_exit.assert_called_once_with(1)
        mock_stderr.assert_called_once_with(
            "Error: DC_API_KEY environment variable is missing.\n"
        )


def test_startup_missing_key_bypassed():
    os.environ["DC_API_KEY_OPTIONAL"] = "true"

    with (
        patch("sys.exit") as mock_exit,
        patch(
            "datacommons_api.services.central_api_client.CentralAPIClient.query_usa_population"
        ) as mock_query,
    ):
        validate_api_key_startup()

        mock_query.assert_not_called()
        mock_exit.assert_not_called()
        assert os.environ.get("_DC_API_KEY_STARTUP_DEGRADED") == "true"
        assert os.environ.get("_DC_API_KEY_STATUS") == "bypassed"


def test_startup_invalid_key_fails():
    os.environ["DC_API_KEY"] = "invalid-key"

    with (
        patch(
            "datacommons_api.services.central_api_client.CentralAPIClient.query_usa_population",
            side_effect=APIKeyUnauthorizedError("Invalid or expired API key"),
        ) as mock_query,
        patch("sys.exit", side_effect=SystemExit) as mock_exit,
        patch("sys.stderr.write") as mock_stderr,
    ):
        with pytest.raises(SystemExit):
            validate_api_key_startup()

        mock_query.assert_called_once()
        mock_exit.assert_called_once_with(1)
        assert (
            "Error: Provided DC_API_KEY is invalid or expired"
            in mock_stderr.call_args[0][0]
        )


def test_startup_unreachable_fail_open():
    os.environ["DC_API_KEY"] = "valid-key"

    with (
        patch(
            "datacommons_api.services.central_api_client.CentralAPIClient.query_usa_population",
            side_effect=Exception("Connection timeout"),
        ) as mock_query,
        patch("sys.exit") as mock_exit,
    ):
        validate_api_key_startup()

        mock_query.assert_called_once()
        mock_exit.assert_not_called()
        assert os.environ.get("_DC_API_KEY_STARTUP_DEGRADED") == "true"
        assert os.environ.get("_DC_API_KEY_STATUS") == "unverified"


def test_startup_unreachable_fail_closed():
    os.environ["DC_API_KEY"] = "valid-key"
    os.environ["DC_API_KEY_STRICT_VALIDATION"] = "true"

    with (
        patch(
            "datacommons_api.services.central_api_client.CentralAPIClient.query_usa_population",
            side_effect=Exception("Connection timeout"),
        ) as mock_query,
        patch("sys.exit", side_effect=SystemExit) as mock_exit,
        patch("sys.stderr.write") as mock_stderr,
    ):
        with pytest.raises(SystemExit):
            validate_api_key_startup()

        mock_query.assert_called_once()
        mock_exit.assert_called_once_with(1)
        assert (
            "Error: DC_API_KEY verification unreachable and strict validation is enabled"
            in mock_stderr.call_args[0][0]
        )
