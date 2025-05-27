import re
import csv
from typing import List, Dict, Union, Optional, Literal, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class PropertyValue:
  """Represents a property value in MCF with its type and metadata"""
  type: Literal['string', 'boolean', 'number', 'null', 'reference']
  value: Any
  namespace: Optional[str] = None

  def get_value(self) -> Any:
    """Get the properly typed value based on the type"""
    if self.type == 'null':
      return None
    if self.type == 'boolean':
      return bool(self.value)
    if self.type == 'number':
      return float(self.value) if '.' in str(self.value) else int(self.value)
    if self.type == 'reference':
      return f"{self.namespace}:{self.value}" if self.namespace else self.value
    return str(self.value)

  @classmethod
  def from_string(cls, value: str) -> 'PropertyValue':
    """Create a PropertyValue from a string value"""
    value = value.strip()
    # Handle null
    if value.lower() == 'null':
      return cls(type='null', value=None)
      
    # Handle booleans
    if value == 'true':
      return cls(type='boolean', value=True)
    if value == 'false':
      return cls(type='boolean', value=False)
      
    # Handle quoted strings
    if value.startswith('"') and value.endswith('"'):
      return cls(type='string', value=value[1:-1])
      
    # Handle numbers
    try:
      if '.' in value:
        return cls(type='number', value=float(value))
      return cls(type='number', value=int(value))
    except ValueError:
      # Handle references
      if ':' in value:
        namespace, ref = value.split(':', 1)
        return cls(type='reference', value=ref, namespace=namespace)
      # Default to reference with dc: namespace
      return cls(type='reference', value=value, namespace='dc')

@dataclass
class McfNode:
  node_id: str
  properties: Dict[str, List[PropertyValue]] = None

  def __post_init__(self):
    if self.properties is None:
      self.properties = {}
  
  def add_property(self, key: str, values: List[str]):
    """Add a property with its values to the node"""
    # Convert string values to PropertyValue objects
    property_values = [PropertyValue.from_string(v) for v in values]
    self.properties[key] = property_values
