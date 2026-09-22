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

"""Resolution of the Data Commons endpoint that `datacommons client` targets."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

import click
import google.auth
from datacommons_admin.core.utils.models import TerraformStateConfig
from datacommons_admin.core.utils.tf_utils import get_datacommons_service_url
from google.auth.transport.requests import Request
from google.oauth2 import id_token

PUBLIC_API_URL = "https://api.datacommons.org"
API_KEY_ENV_VAR = "DATACOMMONS_API_KEY"

_API_KEY_HINT = (
    "The endpoint rejected the request credentials.\n"
    f"Pass --api-key, or set the {API_KEY_ENV_VAR} environment variable. "
    "API keys are issued at https://apikeys.datacommons.org.\n"
    "If the endpoint is a private DCP instance, target it with "
    "--project-id and --instance-name instead."
)

_IAM_HINT = (
    "Google Cloud rejected the request credentials.\n"
    "Authenticate with 'gcloud auth application-default login' and ensure your "
    "account holds the 'roles/run.invoker' role on the Data Commons service."
)


class ApiLayout(Enum):
    """How a Data Commons deployment lays out its REST API paths.

    The public Data Commons API serves each API at the root of the host, while
    a self-hosted DCP instance serves them beneath a `/core/api` prefix.
    """

    ROOT = "root"
    CORE_API = "core_api"


@dataclass(frozen=True)
class ConnectionOptions:
    """Raw endpoint-targeting options collected from the command line."""

    url: str | None = None
    project_id: str | None = None
    instance_name: str | None = None
    api_key: str | None = None

    def __post_init__(self) -> None:
        """Validates that the options select exactly one endpoint."""
        if not self.targets_instance:
            return

        if self.url:
            raise click.UsageError(
                "--url cannot be combined with --project-id/--instance-name.\n"
                "Use --url for a directly reachable endpoint, or "
                "--project-id with --instance-name to resolve a private DCP instance."
            )
        if not (self.project_id and self.instance_name):
            raise click.UsageError(
                "--project-id and --instance-name must be provided together "
                "to resolve a DCP instance."
            )

    @property
    def targets_instance(self) -> bool:
        """Reports whether the options select a DCP instance by name."""
        return bool(self.project_id or self.instance_name)


@dataclass(frozen=True)
class Connection:
    """A resolved Data Commons endpoint and the credentials used to reach it."""

    base_url: str
    headers: Mapping[str, str]
    preferred_layout: ApiLayout
    auth_hint: str


def resolve_connection(options: ConnectionOptions) -> Connection:
    """Resolves the endpoint that a client command should query.

    Exactly one of two targeting modes applies:

    * `--project-id` with `--instance-name` looks the service URL up in the
      instance's Terraform state and authenticates with Google Cloud IAM. This
      is the only way to reach an instance whose URL is private.
    * `--url` (defaulting to the public Data Commons API) talks to a directly
      reachable endpoint, authenticating with an API key when one is supplied.
    """
    if options.targets_instance:
        return _connect_to_instance(options.project_id, options.instance_name)
    return _connect_to_url(options.url or PUBLIC_API_URL, options.api_key)


def _connect_to_instance(project_id: str, instance_name: str) -> Connection:
    """Resolves a DCP instance from its Terraform state, authenticated via IAM."""
    config = TerraformStateConfig(project_id=project_id, instance_name=instance_name)
    base_url = normalize_url(get_datacommons_service_url(config))
    return Connection(
        base_url=base_url,
        headers={"Authorization": f"Bearer {fetch_id_token(base_url)}"},
        preferred_layout=ApiLayout.CORE_API,
        auth_hint=_IAM_HINT,
    )


def _connect_to_url(url: str, api_key: str | None) -> Connection:
    """Targets an endpoint by URL, authenticated with an API key when provided."""
    return Connection(
        base_url=normalize_url(url),
        headers={"X-API-Key": api_key} if api_key else {},
        preferred_layout=ApiLayout.ROOT,
        auth_hint=_API_KEY_HINT,
    )


def normalize_url(url: str) -> str:
    """Normalizes an endpoint URL, defaulting a bare host to HTTPS.

    Accepts values such as `api.datacommons.org`, `https://api.datacommons.org`
    and `http://localhost:8080`.
    """
    candidate = url.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise click.UsageError(
            f"Invalid endpoint URL '{url}'. "
            "Expected a host such as 'api.datacommons.org' or a full http(s) URL."
        )
    return candidate.rstrip("/")


def fetch_id_token(audience: str) -> str:
    """Mints a Google-signed OIDC token for an IAM-protected Cloud Run service."""
    try:
        credentials, _ = google.auth.default()
        request = Request()

        # Refreshing user Application Default Credentials populates `id_token`.
        # Service accounts and compute metadata instead require an explicit,
        # audience-scoped token exchange.
        if not getattr(credentials, "id_token", None):
            credentials.refresh(request)
        return getattr(credentials, "id_token", None) or id_token.fetch_id_token(
            request, audience
        )
    except Exception as e:
        raise click.ClickException(
            f"Failed to obtain Google Cloud credentials for '{audience}': {e}\n"
            "Authenticate with 'gcloud auth application-default login'."
        ) from e
