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

from collections.abc import Generator
from io import StringIO
from typing import IO

from datacommons.schema.models.mcf import McfNode


class MCFParseError(Exception):
    """Raised when MCF parsing fails"""

    # Error messages
    INVALID_LINE_FORMAT = "Invalid line format: {}"
    NODE_START_REQUIRED = "Node block must start with Node declaration"
    EMPTY_NODE_ID = "Node ID cannot be empty"
    MULTIPLE_NODE_DECLARATIONS = "Multiple Node declarations in single block"
    PROPERTY_BEFORE_NODE = "Property found before Node declaration"
    MISSING_NODE_DECLARATION = "Node block missing Node declaration"
    UNCLOSED_QUOTE = "Unclosed quote in value: {}"
    PROPERTY_ERROR = "Error adding property {}: {}"


# Constants
EXPECTED_PARTS = 2


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
    block_lines: list[str] = []

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


def _process_mcf_block(lines: list[str]) -> McfNode | None:
    """
    Processes lines from a text MCF node block and returns a McfNode object

    Returns:
      A McfNode object if the block is valid, None otherwise
    """
    if not lines:
        return None

    node = None
    for index, raw_line in enumerate(lines):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue

        # Split on first colon
        parts = stripped_line.split(":", 1)
        if len(parts) != EXPECTED_PARTS:
            error_msg = MCFParseError.INVALID_LINE_FORMAT.format(stripped_line)
            raise MCFParseError(error_msg)

        key = parts[0].strip()
        value = parts[1].strip()

        # Handle Node declaration
        if index == 0 and key != "Node":
            raise MCFParseError(MCFParseError.NODE_START_REQUIRED)
        if key == "Node":
            if not value:
                raise MCFParseError(MCFParseError.EMPTY_NODE_ID)
            if node is not None:
                raise MCFParseError(MCFParseError.MULTIPLE_NODE_DECLARATIONS)
            node = McfNode(node_id=value)
            continue

        # Ensure we have a current node
        if node is None:
            raise MCFParseError(MCFParseError.PROPERTY_BEFORE_NODE)

        # Parse values (handle comma-separated lists)
        values = _split_preserving_quotes(value)
        try:
            node.add_property(key, values)
        except ValueError as e:
            error_msg = MCFParseError.PROPERTY_ERROR.format(key, str(e))
            raise MCFParseError(error_msg) from e

    # Ensure we found a Node declaration
    if node is None:
        raise MCFParseError(MCFParseError.MISSING_NODE_DECLARATION)

    return node


def _split_preserving_quotes(text: str) -> list[str]:
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
    current_value = ""
    in_quotes = False

    for char in text:
        if char == '"':
            in_quotes = not in_quotes
            current_value += char
        elif char == "," and not in_quotes:
            values.append(current_value.strip())
            current_value = ""
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
            error_msg = MCFParseError.UNCLOSED_QUOTE.format(value)
            raise MCFParseError(error_msg)
    return values
