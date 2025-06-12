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

from sqlalchemy.orm import Session
from datacommons.db.models.node import NodeModel

class NodeRepository:
  """
  Repository for managing nodes in the database.
  """
  def __init__(self, session: Session):
    self.session = session

  def get_node(self, subject_id: str) -> NodeModel:
    return self.session.query(NodeModel).filter(NodeModel.subject_id == subject_id).first()

  def create_node(self, node: NodeModel) -> NodeModel:
    self.session.add(node)
    self.session.commit()
    return node
