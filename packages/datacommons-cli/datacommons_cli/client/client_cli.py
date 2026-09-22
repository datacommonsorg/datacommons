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

"""`datacommons client` commands for querying Data Commons APIs."""

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path

import click

from datacommons_cli.client.connection import (
    API_KEY_ENV_VAR,
    PUBLIC_API_URL,
    Connection,
    ConnectionOptions,
    resolve_connection,
)
from datacommons_cli.client.sdmx_client import (
    SdmxAPIError,
    SdmxClient,
    SdmxClientError,
    parse_filters,
)

_AUTH_FAILURE_STATUSES = (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN)


@click.group(name="client")
@click.option(
    "--url",
    default=None,
    help=(
        "Endpoint to query, as a host or full URL "
        f"(e.g. api.datacommons.org, http://localhost:8080). Defaults to {PUBLIC_API_URL}."
    ),
)
@click.option(
    "--project-id",
    default=None,
    help="GCP project of a DCP instance to resolve from its Terraform state.",
)
@click.option(
    "--instance-name",
    default=None,
    help="Name of the DCP instance to resolve from its Terraform state.",
)
@click.option(
    "--api-key",
    default=None,
    envvar=API_KEY_ENV_VAR,
    help=(
        "API key for the endpoint. "
        f"Defaults to the {API_KEY_ENV_VAR} environment variable."
    ),
)
@click.pass_context
def client(
    ctx: click.Context,
    url: str | None,
    project_id: str | None,
    instance_name: str | None,
    api_key: str | None,
) -> None:
    """Query the APIs of a Data Commons instance.

    Commands target the public Data Commons API at https://api.datacommons.org
    by default, which requires an API key. Use --url to query any other
    reachable endpoint.

    A DCP instance deployed with a private URL cannot be reached this way.
    Select it with --project-id and --instance-name instead: its service URL is
    read from the instance's Terraform state and requests are authenticated
    with your Google Cloud credentials.
    """
    ctx.obj = ConnectionOptions(
        url=url,
        project_id=project_id,
        instance_name=instance_name,
        api_key=api_key,
    )


def _sdmx_query_options(command: Callable) -> Callable:
    """Applies the options shared by every SDMX query command."""
    options = [
        click.option(
            "--variable",
            "-v",
            required=True,
            help="The statistical variable measured (e.g. Count_Person).",
        ),
        click.option(
            "--filter",
            "-f",
            "filters",
            multiple=True,
            help=(
                "Constrain a dimension or attribute, as key=value "
                "(e.g. -f observationAbout=country/FRA). Repeatable; "
                "comma-separated values match any of them."
            ),
        ),
        click.option(
            "--output",
            "-o",
            type=click.Path(dir_okay=False, writable=True),
            default=None,
            help="Write the response to this file instead of stdout.",
        ),
        click.option(
            "--log/--no-log",
            default=True,
            show_default=True,
            help="Request server-side SDMX execution logs (X-Log-SDMX header).",
        ),
        click.option(
            "--multi-entity/--no-multi-entity",
            default=True,
            show_default=True,
            help=(
                "Query across multi-entity schemas (X-Use-Multi-Entity-Schema header)."
            ),
        ),
        click.option(
            "--accept",
            default=None,
            help="Override the HTTP Accept header.",
        ),
    ]
    for option in reversed(options):
        command = option(command)
    return command


@client.command(name="sdmx-data")
@_sdmx_query_options
@click.pass_obj
def sdmx_data(
    options: ConnectionOptions,
    variable: str,
    filters: tuple[str, ...],
    output: str | None,
    *,
    log: bool,
    multi_entity: bool,
    accept: str | None,
) -> None:
    """Fetch statistical observations as SDMX-CSV.

    \b
    Examples:
      datacommons client sdmx-data -v Count_Person -f observationAbout=country/USA
      datacommons client --project-id my-project --instance-name prod \\
          sdmx-data -v FinancialTrade -f sourceCountry=country/FRA
    """
    constraints = _parse_filters(filters)
    connection = _connect(options)

    with _reporting_errors(connection):
        content = SdmxClient(connection).get_data(
            variable,
            constraints,
            log=log,
            multi_entity=multi_entity,
            accept=accept,
        )

    _write_output(content, output)


@client.command(name="sdmx-availability")
@click.argument("component_id")
@_sdmx_query_options
@click.pass_obj
def sdmx_availability(
    options: ConnectionOptions,
    component_id: str,
    variable: str,
    filters: tuple[str, ...],
    output: str | None,
    *,
    log: bool,
    multi_entity: bool,
    accept: str | None,
) -> None:
    """Query the values available for a dimension or attribute.

    COMPONENT_ID is the dimension or attribute to inspect, such as
    `provenance`, `unit` or a custom property like `sourceCountry`.

    \b
    Examples:
      datacommons client sdmx-availability provenance -v Count_Person
      datacommons client sdmx-availability destinationCountry -v FinancialTrade \\
          -f sourceCountry=country/FRA
    """
    constraints = _parse_filters(filters)
    connection = _connect(options)

    with _reporting_errors(connection):
        result = SdmxClient(connection).get_availability(
            component_id,
            variable,
            constraints,
            log=log,
            multi_entity=multi_entity,
            accept=accept,
        )

    content = (
        json.dumps(result, indent=2)
        if isinstance(result, (dict, list))
        else str(result)
    )
    _write_output(content, output)


def _parse_filters(filters: tuple[str, ...]) -> dict[str, list[str]]:
    """Parses `--filter` values, reporting bad input as a CLI error."""
    try:
        return parse_filters(filters)
    except ValueError as e:
        raise click.ClickException(str(e)) from e


def _connect(options: ConnectionOptions) -> Connection:
    """Resolves the target endpoint, reporting progress on stderr.

    Informational output is kept on stderr so that stdout stays a clean stream
    of CSV or JSON that can be piped or redirected.
    """
    if options.targets_instance:
        click.secho(
            f"Resolving instance '{options.instance_name}' from Terraform state...",
            fg="bright_black",
            err=True,
        )

    connection = resolve_connection(options)
    click.secho(f"Querying {connection.base_url}...", fg="bright_black", err=True)
    return connection


@contextmanager
def _reporting_errors(connection: Connection) -> Iterator[None]:
    """Converts client failures into CLI errors, adding hints for auth failures."""
    try:
        yield
    except SdmxAPIError as e:
        detail = (
            f"{e}\n\n{connection.auth_hint}"
            if e.status_code in _AUTH_FAILURE_STATUSES
            else str(e)
        )
        raise click.ClickException(detail) from e
    except SdmxClientError as e:
        raise click.ClickException(str(e)) from e


def _write_output(content: str, output: str | None) -> None:
    """Writes the response to a file, or to stdout when no file is given."""
    if not output:
        click.echo(content)
        return

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    click.secho(f"Wrote output to {path}", fg="green", err=True)
