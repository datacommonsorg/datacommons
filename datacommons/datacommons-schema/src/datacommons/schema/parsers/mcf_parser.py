from io import StringIO
from typing import IO, List, Generator
from datacommons.schema.models.mcf import McfNode


class MCFParseError(Exception):
  """Raised when MCF parsing fails"""
  pass


def parse_mcf_string(content: str) -> Generator[McfNode, None, None]:
  """Parse MCF content and yield Node objects

  Args:
    content: A string containing MCF content

  Returns:
    Generator of McfNode objects
  """
  return parse_mcf(StringIO(content))

def parse_mcf(stream: IO[str]) -> Generator[McfNode, None, None]:
  """Parse MCF content and yield Node objects

  Args:
    stream: A stream containing MCF content

  Returns:
    Generator of McfNode objects

  Raises:
    MCFParseError: If MCF content is invalid
  """
  block_lines: List[str] = []

  # Handle file path input
  for raw in stream:
    line = raw.rstrip()
    # skip comments
    if line.lstrip().startswith("#"):
      continue
    # blank line → end of block
    if line == "":
      mcf_node = _process_mcf_block(block_lines)
      if mcf_node is not None:
        yield mcf_node
      block_lines = []
    else:
      block_lines.append(line)
  # final block (if no trailing blank line)
  mcf_node = _process_mcf_block(block_lines)
  if mcf_node is not None:
    yield mcf_node

def _process_mcf_block(lines: List[str]) -> McfNode | None:
  """
  Processes lines from a text MCF node block and returns a McfNode object

  Returns:
    A McfNode object if the block is valid, None otherwise
  """
  if not lines:
    return None
  
  node = None
  for index, line in enumerate(lines):
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
      node = McfNode(node_id=value)
      continue
    
    # Ensure we have a current node
    if node is None:
      raise MCFParseError("Property found before Node declaration")

    # Parse values (handle comma-separated lists)
    values = _split_preserving_quotes(value)
    try:
      node.add_property(key, values)
    except ValueError as e:
      raise MCFParseError(f"Error adding property {key}: {e}")
  
  # Ensure we found a Node declaration
  if node is None:
    raise MCFParseError("Node block missing Node declaration")

  return node

def _split_preserving_quotes(text: str) -> List[str]:
  """
  Splits a string on commas while preserving substrings enclosed in double quotes.

  This function correctly handles quoted sections, ensuring that commas within
  quotes do not result in a split. It also removes the quotes from the final
  output and performs basic error checking for mismatched quotes.

  Example:
    "a, b, c" → ["a", "b", "c"]
    "a, \"b, c\", d" → ["a", "b, c", "d"]

  Args:
    text: The string to be split.

  Returns:
    A list of strings, split by commas, with quotes removed.

  Raises:
    MCFParseError: If the input string contains unclosed or misplaced quotes.
  """
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

  # Check that all quoted values are properly closed
  for value in values:
    if value.startswith('"') and not value.endswith('"'):
      raise MCFParseError(f"Unclosed quote in value: {value}")
  return values
