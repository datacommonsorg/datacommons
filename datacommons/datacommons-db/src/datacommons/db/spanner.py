from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_spanner_engine(project_id: str, instance_id: str, database_name: str):
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

def get_spanner_session(project_id: str, instance_id: str, database_name: str):
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
