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

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
import requests
from click.testing import CliRunner
from datacommons_cli.client.connection import ApiLayout, Connection


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def public_connection() -> Connection:
    """A connection to the public Data Commons API, authenticated by API key."""
    return Connection(
        base_url="https://api.datacommons.org",
        headers={"X-API-Key": "test-key"},
        preferred_layout=ApiLayout.ROOT,
        auth_hint="api key hint",
    )


@pytest.fixture
def instance_connection() -> Connection:
    """A connection to a DCP instance, authenticated by a Google ID token."""
    return Connection(
        base_url="https://dc-service-xyz.run.app",
        headers={"Authorization": "Bearer test-token"},
        preferred_layout=ApiLayout.CORE_API,
        auth_hint="iam hint",
    )


@pytest.fixture
def make_response() -> Callable[..., MagicMock]:
    """Returns a factory building mock `requests.Response` objects."""

    def build(
        status_code: int = 200,
        *,
        text: str = "",
        json_body: object = None,
        content_type: str = "text/csv",
        reason: str = "",
    ) -> MagicMock:
        response = MagicMock(spec=requests.Response)
        response.status_code = status_code
        response.ok = status_code < 400  # noqa: PLR2004
        response.text = text
        response.reason = reason
        response.headers = {"Content-Type": content_type}

        if json_body is None:
            response.json.side_effect = ValueError("no json")
        else:
            response.json.return_value = json_body
        return response

    return build


@pytest.fixture
def make_session() -> Callable[..., MagicMock]:
    """Returns a factory building mock sessions that reply in a fixed order."""

    def build(*responses: MagicMock) -> MagicMock:
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = list(responses)
        return session

    return build
