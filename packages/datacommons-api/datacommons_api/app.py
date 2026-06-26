# Copyright 2026 Google LLC
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

import asyncio
import os
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from datacommons_api.endpoints.routers import node_router
from datacommons_api.core.exceptions import (
    APIKeyUnauthorizedError,
    APIKeyForbiddenError,
)
from datacommons_api.core.logging import get_logger
from datacommons_api.services.central_api_client import CentralAPIClient
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

# Initialize app state from inherited environment variables
app.state.degraded = os.getenv("_DC_API_KEY_STARTUP_DEGRADED", "").lower() == "true"
app.state.api_key_status = os.getenv("_DC_API_KEY_STATUS", "verified")
app.state.api_key_consecutive_failures = 0
app.state.api_key_outage_escalated = False


async def periodic_key_recheck():
    """Background task to periodically re-validate the API key if started degraded."""
    api_key = os.getenv("DC_API_KEY", "").strip()
    if not api_key:
        return

    client = CentralAPIClient(api_key=api_key)

    while app.state.degraded and app.state.api_key_status in ("unverified", "invalid"):
        await asyncio.sleep(60)  # Recheck every 1 minute

        try:
            # Run the synchronous HTTP check in a threadpool to keep it non-blocking
            await run_in_threadpool(client.query_usa_population)

            # Success! Reset state
            app.state.degraded = False
            app.state.api_key_status = "verified"
            app.state.api_key_consecutive_failures = 0
            app.state.api_key_outage_escalated = False

            # Update env vars to sync with any new workers
            os.environ["_DC_API_KEY_STARTUP_DEGRADED"] = "false"
            os.environ["_DC_API_KEY_STATUS"] = "verified"

            logger.info(
                "DC_API_KEY successfully verified by background worker. Exiting degraded mode."
            )
            break  # Stop background worker
        except (APIKeyUnauthorizedError, APIKeyForbiddenError) as e:
            # Key is definitively invalid!
            app.state.api_key_status = "invalid"
            os.environ["_DC_API_KEY_STATUS"] = "invalid"
            logger.critical(
                "CRITICAL: Background validation confirmed the configured DC_API_KEY is invalid/expired: %s. "
                "Please update configuration. Terminating background check.",
                str(e),
            )
            break
        except Exception as e:
            # Network / DNS / 5xx outage
            app.state.api_key_consecutive_failures += 1
            logger.warning(
                "DC_API_KEY background recheck failed (consecutive failures: %d): %s",
                app.state.api_key_consecutive_failures,
                str(e),
            )

            # 30-Minute Outage Escalation Policy
            if (
                app.state.api_key_consecutive_failures >= 30
                and not app.state.api_key_outage_escalated
            ):
                app.state.api_key_outage_escalated = True
                logger.critical(
                    "CRITICAL: DC_API_KEY background validation has failed continuously for 30 minutes. "
                    "Please check your network and API key configuration."
                )


@app.on_event("startup")
async def startup_event():
    """Spawn the background recheck task if server started in degraded mode."""
    if app.state.degraded and app.state.api_key_status == "unverified":
        asyncio.create_task(periodic_key_recheck())


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


# Health and Status Endpoints
@app.get("/healthz", tags=["status"])
@app.get("/status", tags=["status"], include_in_schema=False)
def health_check(response: Response):
    """Expose application health and API key validation status."""
    degraded = app.state.degraded
    api_key_status = app.state.api_key_status
    outage_escalated = app.state.api_key_outage_escalated

    # Case A: Critical / Unhealthy (Definitively invalid key or 30-min outage)
    if api_key_status == "invalid" or outage_escalated:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "degraded": True,
            "api_key_status": api_key_status,
            "critical": True,
            "message": "Data Commons API key validation has failed continuously. Spanner queries remain available.",
        }

    # Case B: Warning / Degraded (Network outage during startup, < 30 mins)
    if degraded and api_key_status == "unverified":
        return {
            "status": "degraded",
            "degraded": True,
            "api_key_status": "unverified",
            "critical": False,
            "message": "Data Commons API key is unverified due to network issues. Operating in degraded fail-open mode.",
        }

    # Case C: Healthy (Verified or Bypassed)
    return {"status": "healthy", "degraded": False, "api_key_status": api_key_status}


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
    for path, path_item in openapi_schema.get("paths", {}).items():
        if path in ("/healthz", "/status"):
            continue
        for method in path_item.values():
            if not isinstance(method, dict):
                continue
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
