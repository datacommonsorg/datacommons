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
