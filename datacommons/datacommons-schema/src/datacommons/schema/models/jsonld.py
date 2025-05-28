from typing import Dict, List, Any, Union, Optional, Annotated
from pydantic import BaseModel, Field, ConfigDict

# Define the possible types for arbitrary fields
class EdgeValue(BaseModel):
  """Represents a value with provenance in a GraphNode edge"""
  id: Optional[str] = Field(None, alias='@id')
  value: Optional[str] = Field(None, alias='@value')
  provenance: Optional[str] = Field(None, alias='@provenance')

  model_config = ConfigDict(
    populate_by_name=True,
    exclude_none=True
  )

class GraphNode(BaseModel):
  id: str = Field(..., alias='@id', description="Unique identifier for this node")
  type: Optional[Union[str, List[str]]] = Field(None, alias='@type', description="RDF type(s) of this node")
  
  # Allow arbitrary fields with our custom types
  model_config = ConfigDict(
    populate_by_name=False,
    extra='allow',
    arbitrary_types_allowed=True,
    exclude_none=True
  )

  def __init__(self, **data):
    # Process arbitrary fields to ensure they match our expected types
    processed_data = {}
    for key, value in data.items():
      if key in ['@id', '@type']:
        processed_data[key] = value
      else:
        processed_data[key] = self._process_field_value(value)
    super().__init__(**processed_data)

  def _process_field_value(self, value: Any) -> Union[EdgeValue, List[EdgeValue]]:
    """Process field values to ensure they match our expected types."""

    # If the value is a dict and has @value, @provenance, or @id, return an EdgeValue
    if isinstance(value, dict):
      return EdgeValue(**value)
    elif isinstance(value, list):
      return [self._process_field_value(item) for item in value]
    return value

  # Example schema for documentation
  @classmethod
  def model_json_schema(cls, **kwargs) -> dict:
    schema = super().model_json_schema(**kwargs)
    schema["example"] = {
      "@id": "http://example.org/person/alice",
      "@type": ["Person", "Agent"],
      "name": {
        "value": "Alice",
        "provenance": "https://example.org/source1"
      },
      "aliases": [
        {
          "value": "Al",
          "provenance": "https://example.org/source1"
        },
        {
          "value": "Alice Smith",
          "provenance": "https://example.org/source2"
        }
      ],
      "home": {
        "value": {
          "@id": "place:geoId/06",
          "@type": ["State"],
          "name": "California"
        },
        "provenance": "https://example.org/source1"
      },
      "friends": [
        {
          "value": {
            "@id": "http://example.org/person/bob",
            "@type": "Person",
            "name": "Bob"
          },
          "provenance": "https://example.org/source1"
        }
      ]
    }
    return schema

# JSON-LD models
class JSONLDDocument(BaseModel):
  context: Dict[str, Any] = Field(..., alias="@context")
  graph: List[GraphNode] = Field(..., alias="@graph")
  
  model_config = ConfigDict(
    populate_by_name=True,
    json_schema_extra={
      "example": {
        "@context": {
          "@vocab": "http://localhost:5000/schema/local/",
          "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
          "rdfs": "http://www.w3.org/2000/01/rdf-schema#"
        },
        "@graph": [
          {
            "@id": "node1", 
            "@type": "Person",
            "name": {
              "@value": "Alice"
            },
            "aliases": [
              {
                "@value": "Al"
              }
            ],
            "home": {
              "@id": "place:geoId/06",
              "@type": ["State"]
            }
          }
        ]
      }
    }
  )
