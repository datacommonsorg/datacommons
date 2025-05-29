# models.py
import sqlalchemy as sa
from sqlalchemy.orm import relationship, deferred
from sqlalchemy.types import String, Text
from .base import Base


class EdgeModel(Base):
  """
  Represents an edge in the graph.
  """
  __tablename__ = 'Edge'
  subject_id = sa.Column(String(1024), sa.ForeignKey('Node.subject_id'), primary_key=True)
  predicate = sa.Column(String(1024), primary_key=True)
  object_id = sa.Column(String(1024), primary_key=True)
  object_value = sa.Column(Text(), nullable=True)
  object_hash = sa.Column(String(64), primary_key=True, nullable=True)
  provenance = sa.Column(String(1024), primary_key=True, nullable=True)
  # Use deferred to avoid loading the node data into memory
  object_value_tokenlist = deferred(sa.Column(Text(), nullable=True)) #  TOKENLIST is a Spanner type, but represented as String in SQLAlchemy

  # Define relationships to both source and target nodes
  source_node = relationship("NodeModel", 
                foreign_keys=[subject_id], 
                back_populates="outgoing_edges")

  # Indexes
  __table_args__ = (
    # Index for object_value lookups
    sa.Index('EdgeByObjectValue', 'object_value'),
  )
  def __repr__(self):
    return f"<EdgeModel(subject_id='{self.subject_id}', predicate='{self.predicate}', object_id='{self.object_id}')>"
