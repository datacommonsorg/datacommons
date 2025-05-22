import unittest
from pathlib import Path
from datacommons.tools.mcf.mcf import parse_mcf, MCFParseError, Node, PropertyValue

class TestMCF(unittest.TestCase):
    def test_basic_mcf_parse(self):
        mcf = """
        Node: Example1
        name: "Test Node"
        prop: value1
        """
        nodes = parse_mcf(mcf)
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
        nodes = parse_mcf(mcf)
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].node_id, "Example1")
        self.assertEqual(nodes[1].node_id, "Example2")

    def test_node_declaration_required(self):
        mcf = """
        name: "Test Node"
        prop: value1
        """
        with self.assertRaises(MCFParseError):
            parse_mcf(mcf)

    def test_single_node_per_block(self):
        mcf = """
        Node: Example1
        Node: Example2
        name: "Test"
        """
        with self.assertRaises(MCFParseError):
            parse_mcf(mcf)

    def test_repeated_properties(self):
        mcf = """
        Node: Example
        prop: value1
        prop: value2
        prop: value3
        """
        nodes = parse_mcf(mcf)
        self.assertEqual(len(nodes[0].properties["prop"]), 3)
        self.assertEqual(nodes[0].properties["prop"][0].get_value(), "dc:value1")
        self.assertEqual(nodes[0].properties["prop"][1].get_value(), "dc:value2")
        self.assertEqual(nodes[0].properties["prop"][2].get_value(), "dc:value3")

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
        nodes = parse_mcf(mcf)
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
            parse_mcf(mcf)

    def test_invalid_numbers(self):
        mcf = """
        Node: Example
        prop: 12.34.56
        """
        with self.assertRaises(ValueError):
            parse_mcf(mcf)

    def test_invalid_boolean(self):
        mcf = """
        Node: Example
        prop: TRUE
        """
        # Should be treated as a reference, not a boolean
        nodes = parse_mcf(mcf)
        self.assertEqual(nodes[0].properties["prop"][0].type, "reference")

    def test_comma_separated_values(self):
        mcf = """
        Node: Example
        prop: value1, "string, with comma", value3
        """
        nodes = parse_mcf(mcf)
        values = nodes[0].properties["prop"]
        self.assertEqual(len(values), 3)
        self.assertEqual(values[1].get_value(), "string, with comma")

    def test_file_input(self):
        # This test assumes the file exists - you may need to create a temporary file
        # or modify the test based on your testing environment
        test_file = Path("test.mcf")
        with open(test_file, "w") as f:
            f.write("Node: Example\nname: Test")
        
        try:
            nodes = parse_mcf(test_file)
            self.assertEqual(len(nodes), 1)
            self.assertEqual(nodes[0].node_id, "Example")
        finally:
            test_file.unlink()
