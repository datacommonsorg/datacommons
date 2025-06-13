# Copyright 2025 Google LLC.
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

import click
import uvicorn

from datacommons.api.app import app
from datacommons.api.core.config import get_config
from datacommons.api.core.logging import get_logger, setup_logging
from datacommons.db.session import initialize_db

setup_logging()
logger = get_logger(__name__)


@click.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--port", default=5000, help="Port to listen on.")
@click.option("--reload", is_flag=True, help="Enable auto-reload.")
def main(host: str, port: int, *, reload: bool = False):
    """Start the FastAPI app with Uvicorn."""
    logger.info("Starting Data Commons...")
    config = get_config()

    # Initialize the database
    logger.info("Initializing database...")
    initialize_db(config.GCP_PROJECT_ID, config.GCP_SPANNER_INSTANCE_ID, config.GCP_SPANNER_DATABASE_NAME)
    logger.info("Starting API server...")
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
    )
