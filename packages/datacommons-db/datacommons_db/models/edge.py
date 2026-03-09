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

# models.py
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from sqlalchemy.types import String

from datacommons_db.models.base import Base
from datacommons_db.models.node import NodeRecord


EDGE_TABLE_NAME = "Edge"

class EdgeRecord(Base):
    """
    Represents an edge in the graph.
    """
    __tablename__ = EDGE_TABLE_NAME

    # Composite Primary Key
    subject_id = sa.Column(String(1024), sa.ForeignKey("Node.subject_id"), primary_key=True)
    predicate = sa.Column(String(1024), sa.ForeignKey("Node.subject_id"), primary_key=True)
    object_id = sa.Column(String(1024), sa.ForeignKey("Node.subject_id"), primary_key=True)
    provenance = sa.Column(String(1024), sa.ForeignKey("Node.subject_id"), primary_key=True)

    # Define relationships to both source and target nodes
    source_node = relationship("NodeRecord", foreign_keys=[subject_id], back_populates="outgoing_edges", lazy="joined")
    target_node = relationship("NodeRecord", foreign_keys=[object_id], back_populates="incoming_edges", lazy="joined")
    
    predicate_node = relationship("NodeRecord", foreign_keys=[predicate], lazy="joined")
    provenance_node = relationship("NodeRecord", foreign_keys=[provenance], lazy="joined")

    # Indexes and constraints
    __table_args__ = (
        sa.Index("InEdge", object_id, predicate, subject_id, provenance),
        sa.Index("EdgeByProvenance", provenance),
        {
            "spanner_interleave_in": "Node",
            "spanner_interleave_on_delete": "NO ACTION",
        },
    )

    def __repr__(self):
        return f"<EdgeRecord(subj='{self.subject_id}', pred='{self.predicate}', obj='{self.object_id}', prov='{self.provenance}')>"

# Explicitly state that EdgeModel depends on NodeRecord for creation order (important for Spanner interleaving)
EdgeRecord.__table__.add_is_dependent_on(NodeRecord.__table__)
