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

import tempfile
import unittest
from pathlib import Path
from datacommons.schema.parsers.mcf_parser import parse_mcf, parse_mcf_string, MCFParseError

class TestMCF(unittest.TestCase):
  def test_basic_mcf_parse(self):
    mcf = """
    Node: Example1
    name: "Test Node"
    prop: value1
    """
    nodes = list(parse_mcf_string(mcf))
    self.assertEqual(len(nodes), 1)
    self.assertEqual(nodes[0].node_id, "Example1")
    self.assertEqual(nodes[0].properties["name"][0].get_value(), "Test Node")
    self.assertEqual(nodes[0].properties["prop"][0].get_value(), "dc:value1")

  def test_multiple_nodes(self):
    mcf = """
    Node: Example1
    name: "Node 1"

    Node: Example2
    name: "Node 2"
    """
    nodes = list(parse_mcf_string(mcf))
    self.assertEqual(len(nodes), 2)
    self.assertEqual(nodes[0].node_id, "Example1")
    self.assertEqual(nodes[1].node_id, "Example2")

  def test_node_declaration_required(self):
    mcf = """
    name: "Test Node"
    prop: value1
    """
    with self.assertRaises(MCFParseError):
      list(parse_mcf_string(mcf))

  def test_single_node_per_block(self):
    mcf = """
    Node: Example1
    Node: Example2
    name: "Test"
    """
    with self.assertRaises(MCFParseError):
      list(parse_mcf_string(mcf))

  def test_repeated_properties(self):
    mcf = """
    Node: Example
    prop: value1
    prop: value2
    prop: value3
    """
    nodes = list(parse_mcf_string(mcf))
    self.assertEqual(len(nodes[0].properties["prop"]), 3)
    self.assertEqual(nodes[0].properties["prop"][0].get_value(), "dc:value1")
    self.assertEqual(nodes[0].properties["prop"][1].get_value(), "dc:value2")
    self.assertEqual(nodes[0].properties["prop"][2].get_value(), "dc:value3")

  def test_node_with_illegal_quotes(self):
    mcf = """
    Node: Example
    prop: "unclosed string
    """
    with self.assertRaises(MCFParseError):
      list(parse_mcf_string(mcf))

  def test_property_value_types(self):
    mcf = """
    Node: Example
    string_prop: "string value"
    bool_prop: true
    bool_prop2: false
    int_prop: 42
    float_prop: 3.14
    null_prop: null
    ref_prop: ns:reference
    """
    nodes = list(parse_mcf_string(mcf))
    props = nodes[0].properties
    
    self.assertEqual(props["string_prop"][0].type, "string")
    self.assertEqual(props["string_prop"][0].get_value(), "string value")
    
    self.assertEqual(props["bool_prop"][0].type, "boolean")
    self.assertTrue(props["bool_prop"][0].get_value())
    self.assertFalse(props["bool_prop2"][0].get_value())
    
    self.assertEqual(props["int_prop"][0].type, "number")
    self.assertEqual(props["int_prop"][0].get_value(), 42)
    
    self.assertEqual(props["float_prop"][0].type, "number")
    self.assertEqual(props["float_prop"][0].get_value(), 3.14)
    
    self.assertEqual(props["null_prop"][0].type, "null")
    self.assertIsNone(props["null_prop"][0].get_value())
    
    self.assertEqual(props["ref_prop"][0].type, "reference")
    self.assertEqual(props["ref_prop"][0].get_value(), "ns:reference")

  def test_invalid_quotes(self):
    mcf = """
    Node: Example
    prop: "unclosed string
    """
    with self.assertRaises(MCFParseError):
      list(parse_mcf_string(mcf))

  def test_floating_point_numbers(self):
    mcf = """
    Node: Example
    prop: 12.34
    """
    nodes = list(parse_mcf_string(mcf))
    self.assertEqual(nodes[0].properties["prop"][0].type, "number")
    self.assertEqual(nodes[0].properties["prop"][0].get_value(), 12.34)

  def test_integer_numbers(self):
    mcf = """
    Node: Example
    prop: 1234
    """
    nodes = list(parse_mcf_string(mcf))
    self.assertEqual(nodes[0].properties["prop"][0].type, "number")
    self.assertEqual(nodes[0].properties["prop"][0].get_value(), 1234)

  def test_invalid_boolean(self):
    mcf = """
    Node: Example
    prop: TRUE
    """
    # Should be treated as a reference, not a boolean
    nodes = list(parse_mcf_string(mcf))
    self.assertEqual(nodes[0].properties["prop"][0].type, "reference")

  def test_comma_separated_values(self):
    mcf = """
    Node: Example
    prop: value1, "string, with comma", value3
    """
    nodes = list(parse_mcf_string(mcf))
    values = nodes[0].properties["prop"]
    self.assertEqual(len(values), 3)
    self.assertEqual(values[1].get_value(), "string, with comma")

  def test_file_input(self):
    with tempfile.NamedTemporaryFile(mode='w') as f:
      f.write("Node: Example\nname: Test")
      f.flush()
      with open(f.name, 'r') as f:
        nodes = list(parse_mcf(f))
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].node_id, "Example")
