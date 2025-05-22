"""JSON-LD validator for Data Commons schema primitives."""

from typing import Dict, List, Optional, Set, Union
from dataclasses import dataclass
from .primitives import (
    PRIMITIVE_TYPES,
    DATA_TYPES,
    RELATIONSHIP_TYPES,
    REQUIRED_FIELDS,
    OPTIONAL_FIELDS,
    PrimitiveType,
    DataType,
    RelationshipType,
)


@dataclass
class ValidationError:
    """Represents a validation error in the JSON-LD document."""
    path: str
    message: str
    value: Optional[Union[str, List, Dict]] = None


class SchemaValidator:
    """Validates JSON-LD documents against Data Commons schema primitives."""

    def __init__(self):
        self.errors: List[ValidationError] = []

    def validate(self, jsonld_doc: Dict) -> bool:
        """Validate a JSON-LD document against schema primitives.
        
        Args:
            jsonld_doc: The JSON-LD document to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        self.errors = []
        return self._validate_node(jsonld_doc)

    def _validate_node(self, node: Dict, path: str = "") -> bool:
        """Validate a single node in the JSON-LD document.
        
        Args:
            node: The node to validate
            path: The path to this node in the document
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not isinstance(node, dict):
            self.errors.append(ValidationError(
                path=path,
                message="Node must be a dictionary",
                value=node
            ))
            return False

        # Validate type
        if "type" not in node:
            self.errors.append(ValidationError(
                path=path,
                message="Missing required field 'type'"
            ))
            return False

        node_type = node["type"]
        if node_type not in PRIMITIVE_TYPES:
            self.errors.append(ValidationError(
                path=path,
                message=f"Invalid type '{node_type}'",
                value=node_type
            ))
            return False

        # Validate required fields
        required = REQUIRED_FIELDS[node_type]
        for field in required:
            if field not in node:
                self.errors.append(ValidationError(
                    path=path,
                    message=f"Missing required field '{field}'"
                ))
                return False

        # Validate optional fields
        optional = OPTIONAL_FIELDS[node_type]
        for field in node:
            if field not in required and field not in optional:
                self.errors.append(ValidationError(
                    path=path,
                    message=f"Unexpected field '{field}'"
                ))
                return False

        # Type-specific validation
        if node_type == PrimitiveType.PROPERTY.value:
            if not self._validate_property(node, path):
                return False

        return True

    def _validate_property(self, node: Dict, path: str) -> bool:
        """Validate a property node.
        
        Args:
            node: The property node to validate
            path: The path to this node in the document
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Validate domain_includes
        if not isinstance(node["domain_includes"], list):
            self.errors.append(ValidationError(
                path=f"{path}.domain_includes",
                message="domain_includes must be a list",
                value=node["domain_includes"]
            ))
            return False

        # Validate range_includes
        if not isinstance(node["range_includes"], list):
            self.errors.append(ValidationError(
                path=f"{path}.range_includes",
                message="range_includes must be a list",
                value=node["range_includes"]
            ))
            return False

        return True

    def get_errors(self) -> List[ValidationError]:
        """Get the list of validation errors.
        
        Returns:
            List[ValidationError]: List of validation errors
        """
        return self.errors
