from typing import Dict, List, Any, Union, Optional
from pydantic import BaseModel, Field, ConfigDict

class GraphNode(BaseModel):
    id: str = Field(..., alias='@id', description="Unique identifier for this node")
    type: Optional[Union[str, List[str]]] = Field(None, alias='@type', description="RDF type(s) of this node")
    # any additional key-value pairs from your JSON-LD node
    extra: Dict[str, Any] = Field(default_factory=dict, description="Other properties on the node")
    model_config = ConfigDict(
        populate_by_name=True,  # Equivalent to allow_population_by_field_name=True
        extra='allow'           # Equivalent to extra=Extra.allow
    )
    # Example schema for documentation (optional, but good practice)
    @classmethod
    def model_json_schema(cls, **kwargs) -> dict:
      schema = super().model_json_schema(**kwargs)
      schema["example"] = {
          "@id": "http://example.org/person/alice",
          "@type": ["Person", "Agent"],
          "name": "Alice", 
          "age": 30,
          "knows": "http://example.org/person/bob"
      }
      return schema

# JSON-LD models
class JSONLDDocument(BaseModel):
  context: Dict[str, Any] = Field(..., alias="@context")
  graph: List[GraphNode] = Field(..., alias="@graph")
  class Config:
    allow_population_by_field_name = True
    schema_extra = {
      "example": {
        "@context": {"@vocab": "http://example.org/"},
        "@graph": [
          {"@id": "node1", "@type": "Node", "name": "Alice"},
          {"@id": "node2", "@type": "friend", "name": "Bob"}
        ]
      }
    }
