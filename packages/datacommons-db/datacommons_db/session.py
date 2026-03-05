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

import logging

from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from datacommons_db.models.base import Base

logger = logging.getLogger(__name__)

REQUIRED_TABLES = ["Edge", "Node", "Observation"]


# DDL for Creating Property Graph
DDL_PROPERTY_GRAPH = """
CREATE OR REPLACE PROPERTY GRAPH DCGraph
  NODE TABLES(
    Node
      KEY(subject_id)
      LABEL Node PROPERTIES(
        bytes,
        name,
        subject_id,
        types,
        value)
  )
  EDGE TABLES(
    Edge
      KEY(subject_id, predicate, object_id, provenance)
      SOURCE KEY(subject_id) REFERENCES Node(subject_id)
      DESTINATION KEY(object_id) REFERENCES Node(subject_id)
      LABEL Edge PROPERTIES(
        object_id,
        predicate,
        provenance,
        subject_id)
  );
"""


def get_engine(project_id: str, instance_id: str, database_name: str) -> Engine:
    """Create and return a SQLAlchemy engine for Cloud Spanner.

    Args:
      project_id: GCP project ID
      instance_id: Cloud Spanner instance ID
      database_name: Cloud Spanner database name

    Returns:
      SQLAlchemy engine configured for Cloud Spanner
    """
    return create_engine(
        f"spanner+spanner:///projects/{project_id}/instances/{instance_id}/databases/{database_name}",
    )


def create_property_graph(engine: Engine):
    """Create the Property Graph schema in the database.

    Args:
      engine: SQLAlchemy engine connected to the database
    """
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(text(DDL_PROPERTY_GRAPH))


def get_session(project_id: str, instance_id: str, database_name: str) -> Session:
    """Create and return a SQLAlchemy session for Cloud Spanner.

    Args:
      project_id: GCP project ID
      instance_id: Cloud Spanner instance ID
      database_name: Cloud Spanner database name

    Returns:
      SQLAlchemy session configured for Cloud Spanner
    """
    engine = get_engine(project_id, instance_id, database_name)
    session = sessionmaker(bind=engine)
    return session()


def initialize_db(project_id: str, instance_id: str, database_name: str):
    """Initialize the Spanner database.

    Args:
      project_id: GCP project ID
      instance_id: Cloud Spanner instance ID
      database_name: Cloud Spanner database name
    """
    engine = get_engine(project_id, instance_id, database_name)

    # Check if database is empty by inspecting existing tables
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Check if all required tables exist
    missing_tables = [
        table for table in REQUIRED_TABLES if table not in existing_tables
    ]
    if missing_tables:
        logger.warning(
            "Missing required tables in database %s: %s", database_name, missing_tables
        )

    # Only create tables if database is completely empty
    if not existing_tables or missing_tables:
        # Import all models so they are properly initialized with the call to Base.metadata.create_all
        logger.info("Creating tables %s in database %s", REQUIRED_TABLES, database_name)
        Base.metadata.create_all(engine)
        create_property_graph(engine)
