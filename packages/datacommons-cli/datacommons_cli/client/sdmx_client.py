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

"""Client for the Data Commons SDMX 3.0 Data and Availability REST APIs."""

from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

import requests

from datacommons_cli.client.connection import ApiLayout, Connection

# The SDMX context, agency, resource and version are fixed for Data Commons;
# the key is always the `*` wildcard.
DATAFLOW = "DC/DF_OBS/1.0.0/*"

DEFAULT_TIMEOUT_SECONDS = 60

# Path beneath which each deployment flavor serves the SDMX API.
_API_ROOTS = {
    ApiLayout.ROOT: "sdmx/v3",
    ApiLayout.CORE_API: "core/api/sdmx/v3",
}


class SdmxClientError(Exception):
    """Base exception for SDMX client operations."""


class SdmxAPIError(SdmxClientError):
    """Raised when an SDMX endpoint returns an HTTP error status."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"SDMX API returned HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


def parse_filters(filters: Sequence[str]) -> dict[str, list[str]]:
    """Parses `key=value` filter strings into a constraint mapping.

    Repeating a key accumulates its values, which the API combines with OR.
    """
    constraints: dict[str, list[str]] = {}
    for item in filters:
        key, separator, value = item.partition("=")
        if not separator or not key.strip():
            raise ValueError(
                f"Invalid filter '{item}'. Expected key=value "
                "(for example: observationAbout=country/FRA)."
            )
        constraints.setdefault(key.strip(), []).append(value.strip())
    return constraints


def build_query_params(
    variable: str,
    constraints: Mapping[str, str | Sequence[str]] | None = None,
) -> dict[str, str]:
    """Builds the `c[<component>]=<values>` query parameters for an SDMX request."""
    params = {"c[variableMeasured]": variable.strip()}
    for component, value in (constraints or {}).items():
        values = [value] if isinstance(value, str) else list(value)
        params[f"c[{component.strip()}]"] = ",".join(str(v).strip() for v in values)
    return params


class SdmxClient:
    """Queries the SDMX 3.0 APIs of a resolved Data Commons endpoint."""

    def __init__(
        self,
        connection: Connection,
        *,
        session: requests.Session | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initializes the client.

        Args:
            connection: The resolved endpoint and its authentication headers.
            session: Optional pre-configured `requests.Session` (used in tests).
            timeout: Per-request timeout in seconds.
        """
        self._connection = connection
        self._session = session or requests.Session()
        self._timeout = timeout
        self._api_root: str | None = None

    @property
    def base_url(self) -> str:
        """Returns the base URL of the endpoint being queried."""
        return self._connection.base_url

    def get_data(
        self,
        variable: str,
        constraints: Mapping[str, str | Sequence[str]] | None = None,
        *,
        response_format: str = "csv",
        log: bool = True,
        multi_entity: bool = True,
        accept: str | None = None,
    ) -> str:
        """Fetches statistical observations for a variable.

        Args:
            variable: The statistical variable measured (e.g. `Count_Person`).
            constraints: Dimension and attribute filters to apply.
            response_format: SDMX response format; defaults to SDMX-CSV.
            log: Request server-side SDMX execution logs.
            multi_entity: Query across multi-entity schemas.
            accept: Optional `Accept` header override.

        Returns:
            The raw response body, SDMX-CSV by default.
        """
        params = build_query_params(variable, constraints)
        if response_format:
            params["format"] = response_format

        response = self._get(
            f"data/dataflow/{DATAFLOW}",
            params,
            log=log,
            multi_entity=multi_entity,
            accept=accept,
        )
        return response.text

    def get_availability(
        self,
        component_id: str,
        variable: str,
        constraints: Mapping[str, str | Sequence[str]] | None = None,
        *,
        log: bool = True,
        multi_entity: bool = True,
        accept: str | None = None,
    ) -> dict[str, Any] | str:
        """Queries the values available for a dimension or attribute.

        Args:
            component_id: The component to inspect (e.g. `provenance`, `unit`).
            variable: The statistical variable measured.
            constraints: Dimension and attribute filters to apply.
            log: Request server-side SDMX execution logs.
            multi_entity: Query across multi-entity schemas.
            accept: Optional `Accept` header override.

        Returns:
            The parsed SDMX-JSON structure, or the raw body if it is not JSON.
        """
        response = self._get(
            f"availability/dataflow/{DATAFLOW}/{component_id}",
            build_query_params(variable, constraints),
            log=log,
            multi_entity=multi_entity,
            accept=accept,
        )

        if "json" not in response.headers.get("Content-Type", ""):
            return response.text
        try:
            return response.json()
        except ValueError:
            return response.text

    def _get(
        self,
        resource: str,
        params: Mapping[str, str],
        *,
        log: bool,
        multi_entity: bool,
        accept: str | None,
    ) -> requests.Response:
        """Fetches an SDMX resource, discovering which API root the endpoint uses."""
        headers = {
            **self._connection.headers,
            "X-Log-SDMX": str(log).lower(),
            "X-Use-Multi-Entity-Schema": str(multi_entity).lower(),
        }
        if accept:
            headers["Accept"] = accept

        response = None
        for api_root in self._candidate_api_roots():
            response = self._send(f"{api_root}/{resource}", params, headers)
            if response.status_code != HTTPStatus.NOT_FOUND:
                self._api_root = api_root
                break

        return self._checked(response)

    def _candidate_api_roots(self) -> tuple[str, ...]:
        """Returns the API roots to try, most likely first.

        A DCP instance serves the SDMX API under `/core/api` while the public
        Data Commons API serves it at the root. The endpoint's preferred layout
        is only a hint, so the other root is retained as a fallback: a 404 from
        the first root transparently retries against the second. A valid SDMX
        query never returns 404, so the status unambiguously signals that the
        endpoint uses the other layout.
        """
        if self._api_root:
            return (self._api_root,)

        preferred = _API_ROOTS[self._connection.preferred_layout]
        fallbacks = (root for root in _API_ROOTS.values() if root != preferred)
        return (preferred, *fallbacks)

    def _send(
        self,
        path: str,
        params: Mapping[str, str],
        headers: Mapping[str, str],
    ) -> requests.Response:
        """Performs a single authenticated GET request."""
        url = f"{self.base_url}/{path}"
        try:
            return self._session.get(
                url, params=params, headers=headers, timeout=self._timeout
            )
        except requests.RequestException as e:
            raise SdmxClientError(
                f"Could not reach the Data Commons endpoint at {url}: {e}"
            ) from e

    @staticmethod
    def _checked(response: requests.Response) -> requests.Response:
        """Returns the response, raising `SdmxAPIError` for error statuses."""
        if response.ok:
            return response
        raise SdmxAPIError(response.status_code, _error_message(response))


def _error_message(response: requests.Response) -> str:
    """Extracts the most informative error message from a failed response.

    Falls back to the HTTP reason phrase so that responses with blank or
    uninformative bodies still describe the failure.
    """
    message = ""
    try:
        payload = response.json()
    except ValueError:
        body = response.text.strip()
        # HTML bodies, such as a proxy or load balancer error page, are too
        # noisy to surface verbatim; leave them to the reason phrase fallback.
        if not body.startswith("<"):
            message = body
    else:
        if isinstance(payload, dict):
            message = str(payload.get("message") or payload.get("error") or "")
            # Surface the raw payload when it has content but no known field.
            if not message.strip() and payload:
                message = response.text
        elif payload is not None:
            message = str(payload)

    return message.strip() or response.reason or "Unknown error"
