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

"""Tests for /healthz and /status endpoints."""

from fastapi.testclient import TestClient
import pytest

from datacommons_api.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    """Reset app state before/after each test."""
    app.state.degraded = False
    app.state.api_key_status = "verified"
    app.state.api_key_consecutive_failures = 0
    app.state.api_key_outage_escalated = False
    yield


def test_health_healthy():
    app.state.degraded = False
    app.state.api_key_status = "verified"

    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "degraded": False,
        "api_key_status": "verified",
    }

    # Test alias `/status`
    response_alias = client.get("/status")
    assert response_alias.status_code == 200
    assert response_alias.json() == response.json()


def test_health_degraded_warning():
    app.state.degraded = True
    app.state.api_key_status = "unverified"
    app.state.api_key_outage_escalated = False

    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["degraded"] is True
    assert data["api_key_status"] == "unverified"
    assert data["critical"] is False
    assert "degraded fail-open mode" in data["message"]


def test_health_unhealthy_invalid_key():
    app.state.degraded = True
    app.state.api_key_status = "invalid"

    response = client.get("/healthz")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["degraded"] is True
    assert data["api_key_status"] == "invalid"
    assert data["critical"] is True
    assert "validation has failed continuously" in data["message"]


def test_health_unhealthy_escalated_outage():
    app.state.degraded = True
    app.state.api_key_status = "unverified"
    app.state.api_key_outage_escalated = True

    response = client.get("/healthz")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["degraded"] is True
    assert data["api_key_status"] == "unverified"
    assert data["critical"] is True
    assert "validation has failed continuously" in data["message"]
