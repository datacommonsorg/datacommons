from sqlalchemy import create_engine, inspect, Engine
from sqlalchemy.orm import sessionmaker, Session
from .base import Base
import logging

def get_spanner_engine(project_id: str, instance_id: str, database_name: str) -> Engine:
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
    # connect_args={'client': spanner.Client(project=project_id)}
  )

def get_spanner_session(project_id: str, instance_id: str, database_name: str) -> Session:
  """Create and return a SQLAlchemy session for Cloud Spanner.
  
  Args:
    project_id: GCP project ID
    instance_id: Cloud Spanner instance ID
    database_name: Cloud Spanner database name
    
  Returns:
    SQLAlchemy session configured for Cloud Spanner
  """
  engine = get_spanner_engine(project_id, instance_id, database_name)
  Session = sessionmaker(bind=engine)
  return Session()

def initialize_db(project_id: str, instance_id: str, database_name: str):
  """Initialize the Spanner database.
  
  Args:
    project_id: GCP project ID
    instance_id: Cloud Spanner instance ID
    database_name: Cloud Spanner database name
  """
  engine = get_spanner_engine(project_id, instance_id, database_name)
  
  # Check if database is empty by inspecting existing tables
  inspector = inspect(engine)
  existing_tables = inspector.get_table_names()

  # Only create tables if database is completely empty
  if not existing_tables:
    logging.info(f"Creating tables in database {database_name}")
    Base.metadata.create_all(engine)
