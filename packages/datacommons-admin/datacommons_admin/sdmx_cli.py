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

import json
import click
import requests

from datacommons_admin.tf_utils import get_datacommons_service_url


def _get_authenticated_session(target_url: str) -> requests.Session:
    """Returns an authenticated requests.Session for the target Cloud Run URL."""
    if "localhost" in target_url or "127.0.0.1" in target_url:
        return requests.Session()

    import json
    import os

    # Try fetching from user Application Default Credentials (ADC)
    adc_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
    if os.path.exists(adc_path):
        try:
            with open(adc_path) as f:
                data = json.load(f)
            if data.get("type") == "authorized_user":
                payload = {
                    "client_id": data["client_id"],
                    "client_secret": data["client_secret"],
                    "grant_type": "refresh_token",
                    "refresh_token": data["refresh_token"],
                }
                res = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=10)
                if res.ok:
                    id_token_val = res.json().get("id_token")
                    if id_token_val:
                        session = requests.Session()
                        session.headers.update({"Authorization": f"Bearer {id_token_val}"})
                        return session
        except Exception:
            pass

    # Fallback to standard google-auth library (e.g. for service accounts / metadata server)
    import google.auth
    from google.oauth2 import id_token
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession

    auth_req = Request()
    try:
        token = id_token.fetch_id_token(auth_req, target_url)
        creds = Credentials(token)
        return AuthorizedSession(creds)
    except Exception as e:
        raise click.ClickException(
            f"Failed to authenticate with Google Cloud. Neither user Application Default Credentials nor service account could generate an ID token for audience '{target_url}': {e}\n"
            "Please ensure you are authenticated by running:\n"
            "  gcloud auth application-default login"
        )


def _build_sdmx_query_params(variable: str, filters: list[str]) -> dict:
    params = {}
    if variable:
        params["c[variableMeasured]"] = variable
    for f in filters:
        if "=" not in f:
            raise click.ClickException(
                f"Invalid filter format '{f}'. Must be in key=value format (e.g. --filter sourceCountry=country/FRA)"
            )
        k, v = f.split("=", 1)
        params[f"c[{k.strip()}]"] = v.strip()
    return params


def _perform_request(
    path: str,
    params: dict,
    accept: str | None,
    log: bool,
    multi_entity: bool,
) -> requests.Response:
    click.secho("Fetching Data Commons service URL from Terraform outputs...", fg="bright_black")
    base_url = get_datacommons_service_url().rstrip("/")
    url = f"{base_url}/{path.lstrip('/')}"

    headers = {
        "X-Use-Multi-Entity-Schema": "true" if multi_entity else "false",
        "X-Log-SDMX": "true" if log else "false",
    }
    if accept:
        headers["Accept"] = accept

    click.secho(f"Sending authenticated request to {url}...", fg="bright_black")
    session = _get_authenticated_session(base_url)

    try:
        response = session.get(url, params=params, headers=headers, timeout=60)
        return response
    except requests.RequestException as e:
        raise click.ClickException(f"Network error connecting to Data Commons service at {url}: {e}")


def _print_response(response: requests.Response) -> None:
    if not response.ok:
        try:
            err_msg = response.json()
            if isinstance(err_msg, dict):
                err_msg = err_msg.get("message") or err_msg.get("error") or response.text
        except ValueError:
            error_text = response.text.strip()
            # If the error response is HTML (e.g. standard nginx or proxy error), just extract response text preview
            if error_text.startswith("<"):
                err_msg = f"HTTP {response.status_code} {response.reason}"
            else:
                err_msg = error_text
        raise click.ClickException(f"SDMX API returned HTTP {response.status_code}: {err_msg}")

    content_type = response.headers.get("Content-Type", "")
    if "json" in content_type:
        try:
            parsed = response.json()
            click.echo(json.dumps(parsed, indent=2))
        except ValueError:
            click.echo(response.text)
    else:
        click.echo(response.text)


@click.group(name="sdmx")
def sdmx() -> None:
    """Query custom SDMX v3 observation APIs."""
    pass


@sdmx.command(name="data")
@click.option(
    "--variable",
    "-v",
    required=True,
    help="The statistical variable measured (e.g. directionalFinancialAid).",
)
@click.option(
    "--filter",
    "-f",
    "filters",
    multiple=True,
    help="Filter observations by dimensions/properties. Format: key=value (e.g. --filter sourceCountry=country/FRA).",
)
@click.option(
    "--log/--no-log",
    default=True,
    show_default=True,
    help="Enable detailed SDMX parsing and execution logs on the server side (X-Log-SDMX header).",
)
@click.option(
    "--multi-entity/--no-multi-entity",
    default=True,
    show_default=True,
    help="Enable querying across multi-entity schemas (X-Use-Multi-Entity-Schema header).",
)
@click.option(
    "--accept",
    help="Override default HTTP Accept header.",
)
def sdmx_data(
    variable: str,
    filters: list[str],
    log: bool,
    multi_entity: bool,
    accept: str | None,
) -> None:
    """Fetch statistical observations from the SDMX Data API."""
    params = _build_sdmx_query_params(variable, filters)
    params["format"] = "csv"

    path = "core/api/sdmx/v3/data/dataflow/DC/DF_OBS/1.0.0/*"
    response = _perform_request(path, params, accept, log, multi_entity)
    _print_response(response)


@sdmx.command(name="availability")
@click.argument(
    "component_id",
    type=str,
    required=True,
)
@click.option(
    "--variable",
    "-v",
    required=True,
    help="The statistical variable measured (e.g. directionalFinancialAid).",
)
@click.option(
    "--filter",
    "-f",
    "filters",
    multiple=True,
    help="Filter observations by constraints. Format: key=value (e.g. --filter sourceCountry=country/FRA).",
)
@click.option(
    "--log/--no-log",
    default=True,
    show_default=True,
    help="Enable detailed SDMX parsing and execution logs on the server side (X-Log-SDMX header).",
)
@click.option(
    "--multi-entity/--no-multi-entity",
    default=True,
    show_default=True,
    help="Enable querying across multi-entity schemas (X-Use-Multi-Entity-Schema header).",
)
@click.option(
    "--accept",
    help="Override default HTTP Accept header (negotiates SDMX structure response).",
)
def sdmx_availability(
    component_id: str,
    variable: str,
    filters: list[str],
    log: bool,
    multi_entity: bool,
    accept: str | None,
) -> None:
    """Query available values for a dimension/attribute (e.g. sourceCountry, unit, viaOrganization)."""
    params = _build_sdmx_query_params(variable, filters)
    path = f"core/api/sdmx/v3/availability/dataflow/DC/DF_OBS/1.0.0/*/{component_id}"
    response = _perform_request(path, params, accept, log, multi_entity)
    _print_response(response)
