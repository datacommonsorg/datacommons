# models.py
import sqlalchemy as sa
from sqlalchemy.types import String
from .base import Base

class ObservationModel(Base):
  """
  Represents a statistical observation of a variable.
  """
  __tablename__ = 'Observation'
  
  variable_measured = sa.Column(String(1024), nullable=False, primary_key=True)
  observation_about = sa.Column(String(1024), nullable=False, primary_key=True) 
  import_name = sa.Column(String(1024), nullable=False, primary_key=True)
  observation_period = sa.Column(String(1024), nullable=True)
  measurement_method = sa.Column(String(1024), nullable=True)
  unit = sa.Column(String(1024), nullable=True)
  scaling_factor = sa.Column(String(1024), nullable=True)
  observations = sa.Column(sa.LargeBinary, nullable=False)
  provenance_url = sa.Column(String(1024), nullable=False)

  def __repr__(self):
    return f"<ObservationModel(variable_measured='{self.variable_measured}', observation_about='{self.observation_about}', import_name='{self.import_name}')>"
