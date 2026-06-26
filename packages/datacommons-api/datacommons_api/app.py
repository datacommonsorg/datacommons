# Copyright 2025 Google LLC.
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

"""Main FastAPI application definition."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field

from datacommons_api.endpoints.routers import node_router
from datacommons_api.core.exceptions import (
    APIKeyUnauthorizedError,
    APIKeyForbiddenError,
)
from datacommons_api.core.logging import get_logger
from . import __version__

logger = get_logger(__name__)

# FastAPI initialization
app = FastAPI(
    title="Data Commons API",
    version=__version__,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    debug=True,
)


# Standardized error response model for OpenAPI documentation
class APIKeyErrorResponse(BaseModel):
    error: str = Field(
        ...,
        description="The error type.",
        json_schema_extra={"example": "Unauthorized"},
    )
    message: str = Field(
        ...,
        description="Actionable explanation of the error.",
        json_schema_extra={
            "example": "The Data Commons API server key is invalid or expired. Please contact the administrator."
        },
    )
    code: str = Field(
        ...,
        description="Standardized error code.",
        json_schema_extra={"example": "API_KEY_UNAUTHORIZED"},
    )


# Exception Handlers
@app.exception_handler(APIKeyUnauthorizedError)
async def api_key_unauthorized_exception_handler(
    request: Request, exc: APIKeyUnauthorizedError
):
    logger.critical(
        "CRITICAL: The configured DC_API_KEY is invalid, expired, or unauthorized. "
        "Please verify your deployment settings."
    )
    return JSONResponse(
        status_code=401,
        content={
            "error": "Unauthorized",
            "message": "The Data Commons API server key is invalid or expired. Please contact the administrator.",
            "code": "API_KEY_UNAUTHORIZED",
        },
    )


@app.exception_handler(APIKeyForbiddenError)
async def api_key_forbidden_exception_handler(
    request: Request, exc: APIKeyForbiddenError
):
    logger.critical(
        "CRITICAL: The configured DC_API_KEY does not have permission to access the central API."
    )
    return JSONResponse(
        status_code=403,
        content={
            "error": "Forbidden",
            "message": "The Data Commons API server key lacks permissions to access the requested resource. Please contact the administrator.",
            "code": "API_KEY_FORBIDDEN",
        },
    )


# Override OpenAPI generator to document 401 & 403 globally
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    # Add 401 and 403 responses to all routes except health checks
    for path, methods in openapi_schema.get("paths", {}).items():
        if path in ("/healthz", "/status"):
            continue
        for method in methods.values():
            method.setdefault("responses", {})
            method["responses"]["401"] = {
                "description": "Unauthorized - API Key is invalid or expired",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/APIKeyErrorResponse"}
                    }
                },
            }
            method["responses"]["403"] = {
                "description": "Forbidden - API Key lacks permissions",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/APIKeyErrorResponse"}
                    }
                },
            }
    openapi_schema.setdefault("components", {}).setdefault("schemas", {})
    openapi_schema["components"]["schemas"]["APIKeyErrorResponse"] = (
        APIKeyErrorResponse.model_json_schema()
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

app.include_router(node_router.router, tags=["nodes"])
