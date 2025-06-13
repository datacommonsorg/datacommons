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
from sqlalchemy.types import ARRAY, String, Text
from .base import Base

class NodeModel(Base):
  """
  Represents a node in the graph.
  """
  __tablename__ = 'Node'
  subject_id = sa.Column(String(1024), primary_key=True, autoincrement=False)
  name = sa.Column(Text(), nullable=True)
  types = sa.Column(ARRAY(String(1024)), nullable=True)

  # Define both outgoing and incoming relationships
  outgoing_edges = relationship("EdgeModel", 
                                foreign_keys="EdgeModel.subject_id", 
                                back_populates="source_node",
                                lazy='joined',
                                cascade="all, delete-orphan")

  def __repr__(self):
    return f"<NodeModel(subject_id='{self.subject_id}', name='{self.name}', types={self.types})>"
