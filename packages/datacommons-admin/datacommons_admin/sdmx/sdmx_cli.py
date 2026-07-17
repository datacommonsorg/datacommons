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
from pathlib import Path

import click

from datacommons_admin.core.clients import SdmxClient, SdmxClientError
from datacommons_admin.core.utils.tf_utils import get_datacommons_service_url


def _get_client() -> SdmxClient:
    """Instantiates an SdmxClient configured with the target Data Commons service URL."""
    click.secho(
        "Fetching Data Commons service URL from Terraform outputs...",
        fg="bright_black",
        err=True,
    )
    base_url = get_datacommons_service_url()
    return SdmxClient(base_url)


def _output_content(content: str, output: str | None = None) -> None:
    """Outputs text or JSON content to a file or stdout."""
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        click.secho(f"Wrote output to {output}", fg="green", err=True)
    else:
        click.echo(content)


@click.group(name="sdmx")
def sdmx() -> None:
    """Query custom SDMX v3 observation APIs."""


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
    help="Filter observations by dimensions/properties. Format: key=value (e.g. --filter observationAbout=country/FRA).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Optional file path to save observations output.",
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
    filters: tuple[str, ...],
    output: str | None,
    *,
    log: bool,
    multi_entity: bool,
    accept: str | None,
) -> None:
    """Fetch statistical observations from the SDMX Data API."""
    try:
        constraints = SdmxClient.parse_filter_strings(filters)
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    client = _get_client()
    click.secho(
        f"Sending authenticated request to {client.base_url}...",
        fg="bright_black",
        err=True,
    )

    try:
        content = client.get_data(
            variable=variable,
            constraints=constraints,
            response_format="csv",
            log=log,
            multi_entity=multi_entity,
            accept=accept,
        )
    except SdmxClientError as e:
        raise click.ClickException(str(e)) from e

    _output_content(content, output)


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
    help="Filter observations by constraints. Format: key=value (e.g. --filter observationAbout=country/FRA).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Optional file path to save availability output.",
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
    filters: tuple[str, ...],
    output: str | None,
    *,
    log: bool,
    multi_entity: bool,
    accept: str | None,
) -> None:
    """Query available values for a dimension/attribute (e.g. unit, donorPlace)."""
    try:
        constraints = SdmxClient.parse_filter_strings(filters)
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    client = _get_client()
    click.secho(
        f"Sending authenticated request to {client.base_url}...",
        fg="bright_black",
        err=True,
    )

    try:
        result = client.get_availability(
            component_id=component_id,
            variable=variable,
            constraints=constraints,
            log=log,
            multi_entity=multi_entity,
            accept=accept,
        )
    except SdmxClientError as e:
        raise click.ClickException(str(e)) from e

    content = (
        json.dumps(result, indent=2)
        if isinstance(result, (dict, list))
        else str(result)
    )
    _output_content(content, output)
