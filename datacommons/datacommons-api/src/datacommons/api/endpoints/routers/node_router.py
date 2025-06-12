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

import traceback
from datacommons.api.core.constants import DEFAULT_NODE_FETCH_LIMIT
from fastapi import APIRouter, Depends, Query
from typing import List
from datacommons.schema.models.jsonld import JSONLDDocument
from datacommons.api.services.graph_service import GraphService
from datacommons.api.core.logging import get_logger
from datacommons.api.endpoints.responses import UpdateResponse
from datacommons.api.endpoints.dependencies import with_graph_service

logger = get_logger(__name__)

router = APIRouter()

# JSON-LD endpoint
@router.get("/nodes/", response_model=JSONLDDocument, response_model_exclude_none=True)
def get_nodes(
  limit: int = DEFAULT_NODE_FETCH_LIMIT,
  type_filter: List[str] = Query(None, alias="type", description="Zero or more types"),
  graph_service: GraphService = Depends(with_graph_service)
) -> JSONLDDocument:
  """
  Get nodes with their edges
  """
  # Get nodes with their edges
  response_document = graph_service.get_graph_nodes(limit=limit, type_filter=type_filter)
  return response_document

@router.post("/nodes/", response_model=UpdateResponse, response_model_exclude_none=True)
def insert_nodes(
  jsonld: JSONLDDocument,
  graph_service: GraphService = Depends(with_graph_service)
) -> UpdateResponse:
  """Insert a JSON-LD document into the database"""
  try:
    graph_service.insert_graph_nodes(jsonld)
    return UpdateResponse(success=True, message=f"Inserted {len(jsonld.graph)} nodes successfully")
  except Exception as e:
    logger.error(f"Error inserting nodes: {e}\n{traceback.format_exc()}")
    return UpdateResponse(success=False, message=str(e))

