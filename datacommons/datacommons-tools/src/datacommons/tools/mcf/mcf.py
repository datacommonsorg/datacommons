import re
import csv
from typing import List, Dict, Union, Optional, Literal, Any
from pathlib import Path
from dataclasses import dataclass

class MCFParseError(Exception):
  """Raised when MCF parsing fails"""
  pass

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
    if value.lower() == 'true':
      return cls(type='boolean', value=True)
    if value.lower() == 'false':
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


def parse_mcf(content: Union[str, Path]) -> List[McfNode]:
  """Parse MCF content and return list of Node objects
  
  Args:
    content: Either a string containing MCF content or a Path to an MCF file
    
  Returns:
    List of Node objects
    
  Raises:
    MCFParseError: If MCF content is invalid
  """
  # Handle file path input
  if isinstance(content, Path):
    try:
      with open(content, 'r') as f:
        content = f.read()
    except Exception as e:
      raise MCFParseError(f"Failed to read MCF file: {e}")
  
  # Split into node blocks
  node_blocks = re.split(r'\n\s*\n+', content.strip())
  
  
  nodes = []
  for block in node_blocks:
    if not block.strip():
      continue
    
    # Skip blocks that are only comments
    if all(line.strip().startswith('#') for line in block.strip().split('\n')):
      continue
    
    current_node = parse_node_block(block)
    nodes.append(current_node)
  
  return nodes


def parse_node_block(block: str) -> McfNode:
  """Parse a node block and return a Node object"""
  # Parse lines in block
  all_lines = block.strip().split('\n')
  # Remove comment lines that start with #
  lines = [line for line in all_lines if not line.strip().startswith('#')]
  node = None
  
  for index, line  in enumerate(lines):
    line = line.strip()
    if not line:
      continue

    # Split on first colon
    parts = line.split(':', 1)
    if len(parts) != 2:
      raise MCFParseError(f"Invalid line format: {line}")
      
    key = parts[0].strip()
    value = parts[1].strip()
    
    # Handle Node declaration
    if index == 0 and key != 'Node':
      raise MCFParseError("Node block must start with Node declaration")
    if key == 'Node':
      if not value:
        raise MCFParseError("Node ID cannot be empty")
      if node is not None:
        raise MCFParseError("Multiple Node declarations in single block")
      node = McfNode(value)
      continue
    
    # Ensure we have a current node
    if node is None:
      raise MCFParseError("Property found before Node declaration")

    # Parse values (handle comma-separated lists)
    values = split_preserving_quotes(value)
    node.add_property(key, values)
  
  # Ensure we found a Node declaration
  if node is None:
    raise MCFParseError("Node block missing Node declaration")
    
  return node

  
def split_preserving_quotes(text):
  """Split text on commas while preserving quoted strings."""
  values = []
  current_value = ''
  in_quotes = False
  
  for char in text:
    if char == '"':
      in_quotes = not in_quotes
      current_value += char
    elif char == ',' and not in_quotes:
      values.append(current_value.strip())
      current_value = ''
    else:
      current_value += char
      
  # Add final value
  if current_value:
    values.append(current_value.strip())
    
  # Filter out empty values
  values = [v for v in values if v]
  return values
