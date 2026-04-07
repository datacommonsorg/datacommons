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

from datacommons_api.app import app
from datacommons_api.core.config import get_config, initialize_config
from datacommons_api.core.logging import get_logger, setup_logging
from datacommons_db.session import get_session
from datacommons_api.services.graph_service import GraphService

setup_logging()
logger = get_logger(__name__)


@click.group()
def api():
    """Data Commons API CLI suite"""
    pass


@api.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--port", default=5000, help="Port to listen on.")
@click.option("--reload", is_flag=True, help="Enable auto-reload.")
@click.option("--gcp-project-id", default="", help="GCP project id.")
@click.option("--gcp-spanner-instance-id", default="", help="GCP Spanner instance id.")
@click.option(
    "--gcp-spanner-database-name", default="", help="GCP Spanner database name."
)
def start(
    host: str,
    port: int,
    reload: bool,
    gcp_project_id: str,
    gcp_spanner_instance_id: str,
    gcp_spanner_database_name: str,
):
    """Start the FastAPI app with Uvicorn."""
    logger.info("Starting Data Commons...")
    config = initialize_config(
        gcp_project_id=gcp_project_id,
        gcp_spanner_instance_id=gcp_spanner_instance_id,
        gcp_spanner_database_name=gcp_spanner_database_name,
    )


    logger.info("Starting API server...")
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
    )


@api.command()
@click.option("--gcp-project-id", help="GCP project id.", required=True)
@click.option(
    "--gcp-spanner-instance-id", help="GCP Spanner instance id.", required=True
)
@click.option(
    "--gcp-spanner-database-name", help="GCP Spanner database name.", required=True
)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def drop_tables(
    gcp_project_id: str,
    gcp_spanner_instance_id: str,
    gcp_spanner_database_name: str,
    yes: bool,
):
    """Drop Node and Edge tables from the graph database."""
    # TODO: Refactor this method to only drop the data from the tables, not the tables themselves.
    if not yes:
        click.confirm(
            "Are you sure you want to drop the Node and Edge tables?", abort=True
        )

    logger.info("Dropping Node and Edge tables from the graph database")
    initialize_config(
        gcp_project_id=gcp_project_id,
        gcp_spanner_instance_id=gcp_spanner_instance_id,
        gcp_spanner_database_name=gcp_spanner_database_name,
    )
    config = get_config()
    db = get_session(
        config.GCP_PROJECT_ID,
        config.GCP_SPANNER_INSTANCE_ID,
        config.GCP_SPANNER_DATABASE_NAME,
    )
    graph_service = GraphService(db)
    graph_service.drop_tables()
    logger.info("Successfully dropped Node and Edge tables")
