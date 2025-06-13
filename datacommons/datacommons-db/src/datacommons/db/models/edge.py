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
