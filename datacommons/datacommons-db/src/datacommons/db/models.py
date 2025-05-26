# models.py
import sqlalchemy as sa
from sqlalchemy.orm import relationship, deferred
from sqlalchemy.types import ARRAY, String, Text
from .base import Base
class NodeModel(Base):
    __tablename__ = 'Node'
    subject_id = sa.Column(String(1024), primary_key=True, autoincrement=False)
    name = sa.Column(Text(), nullable=True)
    types = sa.Column(ARRAY(String(1024)), nullable=True)

    # Define both outgoing and incoming relationships
    outgoing_edges = relationship("EdgeModel", 
                                foreign_keys="EdgeModel.subject_id", 
                                back_populates="source_node",
                                lazy='joined')
    #incoming_edges = relationship("EdgeModel",
    #                            foreign_keys="EdgeModel.object_id",
    #                            back_populates="target_node",
    #                            lazy='joined')

    def __repr__(self):
        return f"<NodeModel(subject_id='{self.subject_id}', name='{self.name}', types={self.types})>"


class EdgeModel(Base):
    __tablename__ = 'Edge'
    subject_id = sa.Column(String(1024), sa.ForeignKey('Node.subject_id'), primary_key=True)
    predicate = sa.Column(String(1024), primary_key=True)
    object_id = sa.Column(String(1024), primary_key=True)
    object_value = sa.Column(Text(), nullable=True)
    object_hash = sa.Column(String(64), primary_key=True)
    provenance = sa.Column(String(1024), primary_key=True)
    # Use deferred to avoid loading the node data into memory
    object_value_tokenlist = deferred(sa.Column(Text(), nullable=True)) #  TOKENLIST is a Spanner type, but represented as String in SQLAlchemy

    # Define relationships to both source and target nodes
    source_node = relationship("NodeModel", 
                             foreign_keys=[subject_id], 
                             back_populates="outgoing_edges")
    #target_node = relationship("NodeModel",
    #                         foreign_keys=[object_id],
    #                         back_populates="incoming_edges")

    # Indexes
    __table_args__ = (
      # Index for object_value lookups
      sa.Index('EdgeByObjectValue', 'object_value'),
    )
    def __repr__(self):
        return f"<EdgeModel(subject_id='{self.subject_id}', predicate='{self.predicate}', object_id='{self.object_id}')>"


class Observation(Base):
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
        return f"<Observation(variable_measured='{self.variable_measured}', observation_about='{self.observation_about}', import_name='{self.import_name}')>"