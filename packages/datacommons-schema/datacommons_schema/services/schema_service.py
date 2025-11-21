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

"""
Schema Service Module.

This module handles the "rules" (schema) for Data Commons. It loads definitions of
what things are (Classes), what properties they can have (Properties), and rules
for validation (Shapes).

Example:
    service = SchemaService()
    with open("my_schema.jsonld") as f:
        service.load_schema(f)
    
    # Now you can check if data is valid
    service.validate_node(my_data_node)
"""

import json
from typing import IO

from datacommons_schema.models.jsonld import GraphNode
from datacommons_schema.models.primitives import rdf, shacl
from datacommons_schema.parsers import jsonld_parser
from pyshacl import validate


class ValidationError(Exception):
    """Raised when data doesn't match the schema rules."""


class SchemaService:
    """A service for defining and validating semantic data.

    This service defines classes, properties, and objects, and constraints
    using RDF Graphs and SHACL. It manages definitions for:
    - Classes (e.g., "Person", "City")
    - Properties (e.g., "name", "population")
    - Shapes (Validation rules, e.g., "A Person must have a name")

    Example:
        from io import StringIO
        from datacommons_schema.models.jsonld import GraphNode

        service = SchemaService()

        # Define a simple Person class and a shape for it
        schema_jsonld = \"\"\"{
            "@context": {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#"
            },
            "@graph": [
                {
                    "@id": "Person",
                    "@type": "rdfs:Class"
                },
                {
                    "@id": "name",
                    "@type": "rdf:Property"
                }
            ]
        }\"\"\"
        service.load_schema(StringIO(schema_jsonld))

        # Create a valid person node
        valid_person_node = GraphNode(id="john_doe", type="Person", properties={"name": "John Doe"})
        is_valid, report = service.validate_node(valid_person_node)
        print(f"Valid person node is valid: {is_valid}") # Expected: True

        # Create an invalid person node (missing name)
        invalid_person_node = GraphNode(id="jane_doe", type="Person")
        is_valid, report = service.validate_node(invalid_person_node)
        print(f"Invalid person node is valid: {is_valid}") # Expected: False
        # print(report) # Uncomment to see the validation details
    """

    def __init__(self) -> None:
        self._classes: dict[str, rdf.RDFSClass] = {}
        self._properties: dict[str, rdf.RDFProperty] = {}
        self._shapes: dict[str, shacl.SHACLNodeShape] = {}

    def load_schema(self, stream: IO[str]) -> None:
        """Reads a schema file and stores the definitions.

        Args:
            stream: An open file containing the schema in JSON-LD format.
        
        Example Input (in the file):
            [
                {"@id": "Person", "@type": "Class"},
                {"@id": "name", "@type": "Property"}
            ]
        """
        resources = jsonld_parser.parse_jsonld(stream)
        for resource in resources:
            if isinstance(resource, rdf.RDFSClass):
                self._classes[resource.id] = resource
            elif isinstance(resource, rdf.RDFProperty):
                self._properties[resource.id] = resource
            elif isinstance(resource, shacl.SHACLNodeShape):
                self._shapes[resource.id] = resource

    def get_class(self, class_id: str) -> rdf.RDFSClass | None:
        """Finds a Class definition by its ID.

        Args:
            class_id: The ID to look up (e.g., "http://schema.org/Person").

        Returns:
            The Class object if found, otherwise None.
        """
        return self._classes.get(class_id)

    def get_property(self, property_id: str) -> rdf.RDFProperty | None:
        """Finds a Property definition by its ID.

        Args:
            property_id: The ID to look up (e.g., "http://schema.org/name").

        Returns:
            The Property object if found, otherwise None.
        """
        return self._properties.get(property_id)

    def get_shape_for_class(self, class_id: str) -> shacl.SHACLNodeShape | None:
        """Finds the validation rules (Shape) for a specific Class.

        Args:
            class_id: The Class ID (e.g., "Person").

        Returns:
            The Shape object if there are rules for this class, otherwise None.
        """
        for shape in self._shapes.values():
            if shape.target_class == class_id:
                return shape
        return None

    def validate_node(self, node: GraphNode) -> None:
        """Checks if a single data node follows all the schema rules.

        This does three main checks:
        1. Does the node have a valid type? (e.g., is "Person" a real class?)
        2. Are the properties valid? (e.g., is "age" a real property?)
        3. Does it pass specific rules? (e.g., "age" must be a number)

        Args:
            node: The data node to check.

        Raises:
            ValidationError: If the node breaks any rules.
        
        Example:
            # If "Person" class requires a "name", this would raise an error:
            node = GraphNode(id="bob", type="Person", age=30) 
            service.validate_node(node) # Raises ValidationError: "Person" must have a "name"
        """
        if not node.type:
            raise ValidationError(f"Node {node.id} has no type.")

        # Check if the node's type is a valid class
        node_types = node.type if isinstance(node.type, list) else [node.type]
        for node_type in node_types:
            if node_type not in self._classes:
                raise ValidationError(
                    f"Node {node.id} has an invalid type: {node_type}"
                )

        # Check if the node's properties are valid
        for prop_name, _ in node.model_dump(by_alias=True, exclude_none=True).items():
            if prop_name not in ["@id", "@type"] and prop_name not in self._properties:
                raise ValidationError(
                    f"Node {node.id} has an invalid property: {prop_name}"
                )

        # SHACL validation
        for node_type in node_types:
            shape = self.get_shape_for_class(node_type)
            if shape:
                data_graph = node.model_dump_json(by_alias=True)
                schema_graph = self.get_schema_graph_json()
                conforms, results_graph, results_text = validate(
                    data_graph,
                    shacl_graph=schema_graph,
                    data_graph_format="json-ld",
                    shacl_graph_format="json-ld",
                )
                if not conforms:
                    raise ValidationError(
                        f"Node {node.id} failed SHACL validation:\n{results_text}"
                    )

    def get_schema_graph_json(self) -> str:
        """Returns the entire schema as a JSON string.
        
        This is mostly used internally for the validation tool (pyshacl).
        """
        graph = []
        for cls in self._classes.values():
            graph.append(cls.model_dump(by_alias=True, exclude_none=True))
        for prop in self._properties.values():
            graph.append(prop.model_dump(by_alias=True, exclude_none=True))
        for shape in self._shapes.values():
            graph.append(shape.model_dump(by_alias=True, exclude_none=True))

        return json.dumps({"@graph": graph})
