from typing import List
from sqlalchemy import text
from sqlalchemy.orm import joinedload
from .models import Node, Edge
from .spanner import get_spanner_engine, get_spanner_session

#PROJECT_ID = "datcom-website-dev"
#INSTANCE_ID = "dan-dc2-dc-spanner"
#DATABASE_NAME = "dc-spanner-db"

PROJECT_ID = "datcom-store"
INSTANCE_ID = "dc-kg-test"
DATABASE_NAME = "dc_graph_5"

session = get_spanner_session(PROJECT_ID, INSTANCE_ID, DATABASE_NAME)


def get_nodes(limit = 100) -> List[Node]:
  try:
    result = session.query(Node).limit(limit).all()
  finally:
    session.close()
  return result

def LEGACY_get_nodes_with_edges(limit = 10, type_filter = None) -> List[Node]:
  if type_filter is None:
    nodes = session.query(Node).options(joinedload(Node.outgoing_edges)).limit(limit).all()
  else:
    nodes = session.query(Node).filter(text(":v IN UNNEST(types)")).params(v=type_filter).options(joinedload(Node.outgoing_edges)).limit(limit).all()
  return nodes

def get_nodes_with_edges(limit=100, type_filter=None) -> List[Node]:
    """Get nodes with both incoming and outgoing edges."""
    try:
        query = session.query(Node)
        
        if type_filter:
            query = query.filter(text(":v IN UNNEST(types)")).params(v=type_filter)
        
        # Load both incoming and outgoing edges
        query = query.options(
            joinedload(Node.outgoing_edges),
            #joinedload(Node.incoming_edges)
        ).limit(limit)
        
        nodes = query.all()
        return nodes
    finally:
        session.close()

def get_edges(limit=100):
    """Get edges with their associated nodes."""
    try:
        return session.query(Edge).limit(limit).all()
    finally:
        session.close()

def test_query():
  engine = get_spanner_engine(PROJECT_ID, INSTANCE_ID, DATABASE_NAME)
  with engine.begin() as connection:
    result = connection.execute(text("SELECT 1"))
    print(result.fetchone())

