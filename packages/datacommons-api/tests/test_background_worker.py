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

"""Tests for background re-validation worker."""

import os
from unittest.mock import patch, MagicMock
import pytest

from datacommons_api.app import app, periodic_key_recheck
from datacommons_api.core.exceptions import APIKeyUnauthorizedError


@pytest.fixture(autouse=True)
def clean_state():
    """Reset app state and environment before/after each test."""
    old_env = dict(os.environ)
    app.state.degraded = False
    app.state.api_key_status = "verified"
    app.state.api_key_consecutive_failures = 0
    app.state.api_key_outage_escalated = False
    os.environ.pop("DC_API_KEY", None)
    os.environ.pop("_DC_API_KEY_STARTUP_DEGRADED", None)
    os.environ.pop("_DC_API_KEY_STATUS", None)
    yield
    os.environ.clear()
    os.environ.update(old_env)


@pytest.mark.asyncio
async def test_background_success_exits_degraded():
    # Setup degraded state
    app.state.degraded = True
    app.state.api_key_status = "unverified"
    os.environ["DC_API_KEY"] = "valid-key"

    # Mock query to succeed
    mock_query = MagicMock(return_value={"data": "ok"})

    with (
        patch(
            "datacommons_api.services.central_api_client.CentralAPIClient.query_usa_population",
            mock_query,
        ),
        patch("asyncio.sleep") as mock_sleep,
    ):
        # Loop will sleep once, then query, succeed, and exit.
        # We don't need to force exit because success sets app.state.degraded = False,
        # which breaks the loop.
        mock_sleep.return_value = None

        await periodic_key_recheck()

        assert app.state.degraded is False
        assert app.state.api_key_status == "verified"
        assert os.environ.get("_DC_API_KEY_STARTUP_DEGRADED") == "false"
        assert os.environ.get("_DC_API_KEY_STATUS") == "verified"
        mock_query.assert_called_once()


@pytest.mark.asyncio
async def test_background_auth_error_sets_invalid():
    app.state.degraded = True
    app.state.api_key_status = "unverified"
    os.environ["DC_API_KEY"] = "invalid-key"

    # Mock query to raise APIKeyUnauthorizedError
    with (
        patch(
            "datacommons_api.services.central_api_client.CentralAPIClient.query_usa_population",
            side_effect=APIKeyUnauthorizedError("Invalid"),
        ),
        patch("asyncio.sleep") as mock_sleep,
    ):
        mock_sleep.return_value = None

        await periodic_key_recheck()

        assert app.state.api_key_status == "invalid"
        assert os.environ.get("_DC_API_KEY_STATUS") == "invalid"
        mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_background_outage_escalates():
    app.state.degraded = True
    app.state.api_key_status = "unverified"
    app.state.api_key_consecutive_failures = 0
    app.state.api_key_outage_escalated = False
    os.environ["DC_API_KEY"] = "valid-key"

    # Mock query to raise a network exception
    with (
        patch(
            "datacommons_api.services.central_api_client.CentralAPIClient.query_usa_population",
            side_effect=Exception("Network error"),
        ),
        patch("asyncio.sleep") as mock_sleep,
    ):
        # We need the loop to run 30 times to trigger escalation.
        # On the 30th sleep call, we force exit the loop.
        iteration = 0

        async def sleep_side_effect(secs):
            nonlocal iteration
            iteration += 1
            if iteration >= 30:
                app.state.degraded = False  # Force exit

        mock_sleep.side_effect = sleep_side_effect

        await periodic_key_recheck()

        assert app.state.api_key_consecutive_failures >= 30
        assert app.state.api_key_outage_escalated is True
