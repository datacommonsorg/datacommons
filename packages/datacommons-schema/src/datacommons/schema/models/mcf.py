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

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field  # Import BaseModel and Field from pydantic

FLOAT_REGEX = r"^-?\d*\.\d+$"
INT_REGEX = r"^-?\d+$"


class PropertyValue(BaseModel):  # Changed from dataclass to BaseModel
    """Represents a property value in MCF with its type and metadata"""

    type: Literal["string", "boolean", "number", "null", "reference"]
    value: Any
    namespace: str | None = None  # Optional fields are handled directly by Pydantic

    def get_value(self) -> Any:
        """Get the properly typed value based on the type"""
        if self.type == "null":
            return None
        if self.type == "boolean":
            return bool(self.value)
        if self.type == "number":
            # Pydantic will handle the initial type conversion, but we need to ensure int/float
            # based on presence of decimal for consistency with original logic.
            # Note: Pydantic's default number parsing might already handle this,
            # but keeping original logic for explicit control.
            if isinstance(self.value, int | float):
                return float(self.value) if isinstance(self.value, float) or "." in str(self.value) else int(self.value)
            return float(self.value) if "." in str(self.value) else int(self.value)
        if self.type == "reference":
            return f"{self.namespace}:{self.value}" if self.namespace else self.value
        return str(self.value)

    @classmethod
    def from_string(cls, value: str) -> "PropertyValue":
        """Create a PropertyValue from a string value"""
        value = value.strip()

        # Handle null
        if value.lower() == "null":
            return cls(type="null", value=None)

        # Handle booleans
        if value == "true":
            return cls(type="boolean", value=True)
        if value == "false":
            return cls(type="boolean", value=False)

        # Handle quoted strings
        if value.startswith('"'):
            try:
                # Use json.loads to properly handle escaped quotes and other special characters
                parsed_value = json.loads(value)
                return cls(type="string", value=parsed_value)
            except json.JSONDecodeError as e:
                raise ValueError("Invalid quoted string value: " + value) from e

        # Handle floating point numbers
        if re.match(FLOAT_REGEX, value):
            return cls(type="number", value=float(value))
        # Handle integers
        if re.match(INT_REGEX, value):
            return cls(type="number", value=int(value))

        # Handle references
        if ":" in value:
            namespace, ref = value.split(":", 1)
            return cls(type="reference", value=ref, namespace=namespace)

        # Default to reference with dc: namespace
        return cls(type="reference", value=value, namespace="dc")


class McfNode(BaseModel):  # Changed from dataclass to BaseModel
    node_id: str
    # Use pydantic.Field with default_factory for mutable defaults like dict
    properties: dict[str, list[PropertyValue]] = Field(default_factory=dict)

    # __post_init__ is not needed in Pydantic for default_factory cases

    def add_property(self, key: str, values: list[str]):
        """Add a property with its values to the node"""
        # Convert string values to PropertyValue objects
        property_values = [PropertyValue.from_string(v) for v in values]
        if key not in self.properties:
            self.properties[key] = []
        self.properties[key].extend(property_values)
