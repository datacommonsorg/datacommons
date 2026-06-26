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

"""Tests for FastAPI exception handlers and OpenAPI documentation."""

from fastapi.testclient import TestClient
import pytest

from datacommons_api.app import app
from datacommons_api.core.exceptions import (
    APIKeyUnauthorizedError,
    APIKeyForbiddenError,
)


# Register temporary test routes on the app
@app.get("/test-unauthorized", tags=["test"])
def route_unauthorized():
    raise APIKeyUnauthorizedError("test unauthorized")


@app.get("/test-forbidden", tags=["test"])
def route_forbidden():
    raise APIKeyForbiddenError("test forbidden")


client = TestClient(app)


def test_unauthorized_exception_handler():
    response = client.get("/test-unauthorized")
    assert response.status_code == 401
    assert response.json() == {
        "error": "Unauthorized",
        "message": "The Data Commons API server key is invalid or expired. Please contact the administrator.",
        "code": "API_KEY_UNAUTHORIZED",
    }


def test_forbidden_exception_handler():
    response = client.get("/test-forbidden")
    assert response.status_code == 403
    assert response.json() == {
        "error": "Forbidden",
        "message": "The Data Commons API server key lacks permissions to access the requested resource. Please contact the administrator.",
        "code": "API_KEY_FORBIDDEN",
    }


def test_openapi_documentation():
    # Force recreation of OpenAPI schema to ensure our custom generator runs
    app.openapi_schema = None
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    # Verify schema definition is present
    components = schema.get("components", {})
    schemas = components.get("schemas", {})
    assert "APIKeyErrorResponse" in schemas

    error_response_schema = schemas["APIKeyErrorResponse"]
    assert "error" in error_response_schema["properties"]
    assert "message" in error_response_schema["properties"]
    assert "code" in error_response_schema["properties"]

    # Verify that standard routes (e.g. from node_router) document 401 and 403
    # Let's find a non-test path in the schema.
    # Our node_router usually registers some paths, let's look for one.
    paths = schema.get("paths", {})

    # We want to find a real route (not our /test-unauthorized or /test-forbidden)
    real_paths = [
        p
        for p in paths.keys()
        if p not in ("/test-unauthorized", "/test-forbidden", "/healthz", "/status")
    ]

    if real_paths:
        target_path = real_paths[0]
        for method_schema in paths[target_path].values():
            responses = method_schema.get("responses", {})
            assert "401" in responses
            assert "403" in responses
            # Verify they reference our APIKeyErrorResponse schema
            assert (
                responses["401"]["content"]["application/json"]["schema"]["$ref"]
                == "#/components/schemas/APIKeyErrorResponse"
            )
            assert (
                responses["403"]["content"]["application/json"]["schema"]["$ref"]
                == "#/components/schemas/APIKeyErrorResponse"
            )
