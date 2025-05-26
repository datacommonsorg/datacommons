from typing import Any, Dict, List, Union, Optional
from pydantic import BaseModel, Field, RootModel
import json


class Context(RootModel):
  """
  Represents a JSON-LD context.
  Can be a dict mapping prefixes or terms to IRIs or definitions.
  """
  root: Union[Dict[str, Any], List[Any]]

  def dict(self, *args, **kwargs) -> Any:
    # Return the raw context structure
    return self.root


class JsonLdNode(BaseModel):
  """
  Represents an individual node in a JSON-LD graph.
  Fields other than @id and @type are allowed and stored dynamically.
  """
  id: Optional[str] = Field(None, alias="@id")
  type: Optional[Union[str, List[str]]] = Field(None, alias="@type")

  class Config:
    allow_population_by_field_name = True
    extra = 'allow'  # Allow arbitrary properties

  def dict(self, *args, **kwargs) -> Dict[str, Any]:
    # Serialize with JSON-LD keywords
    data = super().dict(*args, by_alias=True, **kwargs)
    return data


class JsonLdDocument(BaseModel):
  """
  Represents a full JSON-LD document with @context and @graph.
  """
  context: Context = Field(..., alias="@context")
  graph: List[JsonLdNode] = Field(default_factory=list, alias="@graph")

  class Config:
    allow_population_by_field_name = True
    extra = 'forbid'

  def to_json(self, **kwargs) -> str:
    """Serialize the document to a JSON string."""
    return json.dumps(self.dict(by_alias=True), **kwargs)

  @classmethod
  def from_json(cls, data: Union[str, Dict[str, Any]]) -> "JsonLdDocument":
    """Parse a document from a JSON string or dict."""
    if isinstance(data, str):
      parsed = json.loads(data)
    else:
      parsed = data
    return cls.parse_obj(parsed)

  @classmethod
  def load(cls, path: str, **kwargs) -> "JsonLdDocument":
    """Load a JSON-LD document from a file."""
    with open(path, 'r', encoding='utf-8') as f:
      data = json.load(f)
    return cls.from_json(data)

  def save(self, path: str, **kwargs) -> None:
    """Save the JSON-LD document to a file."""
    with open(path, 'w', encoding='utf-8') as f:
      json.dump(self.dict(by_alias=True), f, **kwargs)
