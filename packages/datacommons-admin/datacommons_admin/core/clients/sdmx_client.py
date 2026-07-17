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

from collections.abc import Mapping, Sequence
from typing import Any

import google.auth
import requests
from google.auth.transport.requests import Request
from google.oauth2 import id_token


class SdmxClientError(Exception):
    """Base exception for SDMX client operations."""


class SdmxAuthError(SdmxClientError):
    """Raised when Google Cloud authentication fails."""


class SdmxAPIError(SdmxClientError):
    """Raised when the SDMX endpoint returns an HTTP error status."""

    def __init__(
        self,
        status_code: int,
        message: str,
        response: requests.Response | None = None,
    ) -> None:
        super().__init__(f"SDMX API returned HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.response = response


class SdmxClient:
    """Client for querying Data Commons Platform SDMX 3.0 REST endpoints.

    Provides high-level methods for fetching statistical observations and querying
    dimension/attribute availability with constraint filtering.
    """

    DEFAULT_DATAFLOW = "DC/DF_OBS/1.0.0/*"

    def __init__(
        self,
        base_url: str,
        *,
        service_account_email: str | None = None,
        session: requests.Session | None = None,
        timeout: int = 60,
    ) -> None:
        """Initializes the SDMX client.

        Args:
            base_url: The root URL of the Data Commons service (e.g. Cloud Run URL).
            service_account_email: Optional service account email to impersonate.
            session: Optional pre-configured requests.Session (e.g. for testing).
            timeout: Default HTTP request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.service_account_email = service_account_email
        self.timeout = timeout
        self._session = session or self._create_authenticated_session()

    @property
    def session(self) -> requests.Session:
        """Returns the active requests.Session."""
        return self._session

    def _create_authenticated_session(self) -> requests.Session:
        """Builds an authenticated requests.Session for the target service URL."""
        if "localhost" in self.base_url or "127.0.0.1" in self.base_url:
            return requests.Session()

        try:
            base_credentials, _ = google.auth.default()
            auth_req = Request()

            if self.service_account_email:
                from google.auth import impersonated_credentials

                target_credentials = impersonated_credentials.Credentials(
                    source_credentials=base_credentials,
                    target_principal=self.service_account_email,
                    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                creds = impersonated_credentials.IDTokenCredentials(
                    target_credentials=target_credentials,
                    target_audience=self.base_url,
                    include_email=True,
                )
                token = creds.token
                if not token:
                    creds.refresh(auth_req)
                    token = creds.token
            else:
                # For user Application Default Credentials, refreshing populates creds.id_token.
                if hasattr(base_credentials, "refresh") and not getattr(
                    base_credentials, "id_token", None
                ):
                    base_credentials.refresh(auth_req)

                token = getattr(base_credentials, "id_token", None)
                # For service accounts / compute environments, fetch audience-specific ID token.
                if not token:
                    token = id_token.fetch_id_token(auth_req, self.base_url)

            session = requests.Session()
            session.headers["Authorization"] = f"Bearer {token}"
            return session

        except Exception as e:
            raise SdmxAuthError(
                f"Failed to authenticate with Google Cloud for audience '{self.base_url}': {e}\n"
                "Please ensure you are authenticated by running:\n"
                "  gcloud auth application-default login"
            ) from e

    @staticmethod
    def parse_filter_strings(
        filter_strings: Sequence[str],
    ) -> dict[str, list[str]]:
        """Parses a sequence of key=value filter strings into a constraint dictionary.

        Multiple values for the same key are grouped into a list.
        """
        constraints: dict[str, list[str]] = {}
        for f in filter_strings:
            if "=" not in f:
                raise ValueError(
                    f"Invalid filter format '{f}'. Must be in key=value format (e.g. observationAbout=country/FRA)"
                )
            k, v = f.split("=", 1)
            key = k.strip()
            val = v.strip()
            constraints.setdefault(key, []).append(val)
        return constraints

    @staticmethod
    def build_query_params(
        variable: str | None = None,
        constraints: Mapping[str, str | Sequence[str]] | None = None,
        extra_params: Mapping[str, Any] | None = None,
    ) -> dict[str, str]:
        """Builds SDMX URL query parameters from variable and constraint mappings."""
        params: dict[str, str] = {}
        if variable:
            params["c[variableMeasured]"] = variable.strip()

        if constraints:
            for k, v in constraints.items():
                param_key = f"c[{k.strip()}]"
                if isinstance(v, (list, tuple, set)):
                    val_str = ",".join(str(item).strip() for item in v)
                else:
                    val_str = str(v).strip()

                if param_key in params:
                    params[param_key] = f"{params[param_key]},{val_str}"
                else:
                    params[param_key] = val_str

        if extra_params:
            for k, v in extra_params.items():
                params[k] = str(v)

        return params

    def request(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        *,
        log: bool = True,
        multi_entity: bool = True,
        accept: str | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        """Executes an authenticated HTTP GET request against the SDMX service."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        req_headers = {
            "X-Use-Multi-Entity-Schema": "true" if multi_entity else "false",
            "X-Log-SDMX": "true" if log else "false",
        }
        if accept:
            req_headers["Accept"] = accept
        if headers:
            req_headers.update(headers)

        req_timeout = timeout if timeout is not None else self.timeout

        try:
            response = self._session.get(
                url, params=params, headers=req_headers, timeout=req_timeout
            )
        except requests.RequestException as e:
            raise SdmxClientError(
                f"Network error connecting to Data Commons service at {url}: {e}"
            ) from e

        if not response.ok:
            try:
                err_data = response.json()
                if isinstance(err_data, dict):
                    err_msg = (
                        err_data.get("message")
                        or err_data.get("error")
                        or response.text
                    )
                else:
                    err_msg = str(err_data)
            except (ValueError, TypeError):
                err_text = response.text.strip()
                if err_text.startswith("<"):
                    err_msg = f"HTTP {response.status_code} {response.reason}"
                else:
                    err_msg = err_text
            raise SdmxAPIError(response.status_code, err_msg, response=response)

        return response

    def get_data(
        self,
        variable: str,
        constraints: Mapping[str, str | Sequence[str]] | None = None,
        *,
        response_format: str = "csv",
        log: bool = True,
        multi_entity: bool = True,
        accept: str | None = None,
        dataflow: str = DEFAULT_DATAFLOW,
    ) -> str:
        """Fetches statistical observations from the SDMX Data API.

        Args:
            variable: The statistical variable measured (e.g. directionalFinancialAid).
            constraints: Mapping of dimension/attribute filter constraints.
            response_format: SDMX data response format (defaults to 'csv').
            log: Enable detailed server-side SDMX execution logging (X-Log-SDMX header).
            multi_entity: Enable querying across multi-entity schemas.
            accept: Optional Accept HTTP header override.
            dataflow: SDMX dataflow path component.

        Returns:
            The raw observation response text (typically CSV).
        """
        extra = {"format": response_format} if response_format else None
        params = self.build_query_params(
            variable=variable,
            constraints=constraints,
            extra_params=extra,
        )
        path = f"core/api/sdmx/v3/data/dataflow/{dataflow.lstrip('/')}"
        response = self.request(
            path,
            params=params,
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
        dataflow: str = DEFAULT_DATAFLOW,
    ) -> dict[str, Any] | str:
        """Queries available values for a dimension or attribute.

        Args:
            component_id: Dimension or attribute to query (e.g. unit, donorPlace).
            variable: The statistical variable measured.
            constraints: Mapping of filter constraints.
            log: Enable detailed server-side SDMX execution logging.
            multi_entity: Enable querying across multi-entity schemas.
            accept: Optional Accept HTTP header override.
            dataflow: SDMX dataflow path component.

        Returns:
            Parsed JSON dictionary containing dataConstraints, or raw text if non-JSON.
        """
        params = self.build_query_params(
            variable=variable, constraints=constraints
        )
        path = f"core/api/sdmx/v3/availability/dataflow/{dataflow.lstrip('/')}/{component_id}"
        response = self.request(
            path,
            params=params,
            log=log,
            multi_entity=multi_entity,
            accept=accept,
        )

        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type:
            try:
                return response.json()
            except ValueError:
                pass
        return response.text
