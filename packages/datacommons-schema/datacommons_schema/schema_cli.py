import sys

import click

from datacommons_schema.converters.mcf_to_jsonld import mcf_nodes_to_jsonld
from datacommons_schema.parsers.mcf_parser import parse_mcf_string


@click.group()
def cli():
    """Data Commons Schema Parsing CLI"""


@cli.command()
@click.argument("mcf_file", type=click.Path(exists=True))
@click.option("--namespace", "-n", help='Namespace to inject into JSONLD output (e.g. "schema:https://schema.org/")')
@click.option("--outfile", "-o", type=click.Path(), help="Output file path (defaults to stdout)")
@click.option(
    "--compact",
    "-c",
    is_flag=True,
    help="Output compact JSON-LD format without type information, using only literal values or object references",
)
def mcf2jsonld(mcf_file, namespace, outfile, *, compact: bool = False):
    """Convert MCF file to JSONLD format"""
    # Read MCF file
    with open(mcf_file) as f:
        mcf_content = f.read()
    # Convert nodes to JSONLD
    mcf_nodes = parse_mcf_string(mcf_content)
    jsonld = mcf_nodes_to_jsonld(mcf_nodes, compact=compact)

    # Add namespace if provided
    if namespace:
        try:
            ns_prefix, ns_url = namespace.split(":", 1)
            jsonld.context[ns_prefix] = ns_url
        except ValueError:
            click.echo("Error: Invalid namespace format. Expected format: prefix:url", err=True)
            sys.exit(1)

    # Convert to formatted JSON string
    output = jsonld.model_dump_json(indent=2)

    # Write to file or stdout
    if outfile:
        with open(outfile, "w") as f:
            f.write(output)
    else:
        click.echo(output)
