import click
import uvicorn
from .app import app
from datacommons.db.spanner import initialize_db
from .config import get_config


@click.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--port", default=5000, help="Port to listen on.")
@click.option("--reload", is_flag=True, help="Enable auto-reload.")
def main(host: str, port: int, reload: bool):
  """Start the FastAPI app with Uvicorn."""
  #   # Initialize the database
  config = get_config()

  # Initialize the database
  print("Initializing database...")
  initialize_db(
      config.SPANNER_PROJECT_ID,
      config.SPANNER_INSTANCE_ID,
      config.SPANNER_DATABASE_NAME
  )
  uvicorn.run(
    app,
    host=host,
    port=port,
    reload=reload,
  )
