# models.py
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, deferred
from sqlalchemy.types import ARRAY, String

Base = declarative_base()

class Node(Base):
    __tablename__ = 'Node'
    subject_id = sa.Column(String(1024), primary_key=True, autoincrement=False)
    name = sa.Column(sa.String(max), nullable=True)
    types = sa.Column(ARRAY(String(1024)), nullable=True)

    # Define both outgoing and incoming relationships
    outgoing_edges = relationship("Edge", 
                                foreign_keys="Edge.subject_id", 
                                back_populates="source_node",
                                lazy='joined')
    #incoming_edges = relationship("Edge",
    #                            foreign_keys="Edge.object_id",
    #                            back_populates="target_node",
    #                            lazy='joined')

    def __repr__(self):
        return f"<Node(subject_id='{self.subject_id}', name='{self.name}', types={self.types})>"


class Edge(Base):
    __tablename__ = 'Edge'
    subject_id = sa.Column(String(1024), sa.ForeignKey('Node.subject_id'), primary_key=True)
    predicate = sa.Column(String(1024), primary_key=True)
    object_id = sa.Column(String(1024), primary_key=True)
    object_value = sa.Column(sa.String(max), nullable=True)
    object_hash = sa.Column(String(64), primary_key=True)
    provenance = sa.Column(String(1024), primary_key=True)
    # Use deferred to avoid loading the node data into memory
    object_value_tokenlist = deferred(sa.Column(sa.String(max), nullable=True)) #  TOKENLIST is a Spanner type, but represented as String in SQLAlchemy

    # Define relationships to both source and target nodes
    source_node = relationship("Node", 
                             foreign_keys=[subject_id], 
                             back_populates="outgoing_edges")
    #target_node = relationship("Node",
    #                         foreign_keys=[object_id],
    #                         back_populates="incoming_edges")

    def __repr__(self):
        return f"<Edge(subject_id='{self.subject_id}', predicate='{self.predicate}', object_id='{self.object_id}')>"
