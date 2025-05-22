import click
from .app import app

@click.command()
def main():
  """A simple hello CLI."""
  click.echo(f"Hello, world THE API CLI!!")
  app.run(host="0.0.0.0", port=5000, debug=True)
