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

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# Define the possible types for arbitrary fields
class GraphNodePropertyValue(BaseModel):
    """Represents a value with provenance in a GraphNode edge"""

    id: str | None = Field(None, alias="@id")
    value: str | None = Field(None, alias="@value")
    provenance: str | None = Field(None, alias="@provenance")

    model_config = ConfigDict(populate_by_name=True, exclude_none=True)


class GraphNode(BaseModel):
    id: str = Field(..., alias="@id", description="Unique identifier for this node")
    type: str | list[str] | None = Field(None, alias="@type", description="RDF type(s) of this node")

    # Allow arbitrary fields with our custom types
    model_config = ConfigDict(populate_by_name=False, extra="allow", arbitrary_types_allowed=True, exclude_none=True)

    def __init__(self, **data):
        # Process arbitrary fields to ensure they match our expected types
        processed_data = {}
        for key, value in data.items():
            # Process named fields
            if key in ["@id", "@type"]:
                processed_data[key] = value
            # Process arbitrary property fields
            else:
                processed_data[key] = self._process_field_value(value)
        super().__init__(**processed_data)

    def _process_field_value(self, value: Any) -> GraphNodePropertyValue | list[GraphNodePropertyValue]:
        """Process field values to ensure they match our expected types."""

        # If the value is a dict and has @value, @provenance, or @id, return a GraphNodePropertyValue
        if isinstance(value, dict):
            return GraphNodePropertyValue(**value)
        if isinstance(value, list):
            return [self._process_field_value(item) for item in value]
        return value

    # Example schema for documentation
    @classmethod
    def model_json_schema(cls, **kwargs) -> dict:
        schema = super().model_json_schema(**kwargs)
        schema["example"] = {
            "@id": "http://example.org/person/alice",
            "@type": ["Person", "Agent"],
            "name": {"value": "Alice", "provenance": "https://example.org/source1"},
            "aliases": [
                {"value": "Al", "provenance": "https://example.org/source1"},
                {"value": "Alice Smith", "provenance": "https://example.org/source2"},
            ],
            "home": {
                "value": {"@id": "place:geoId/06", "@type": ["State"], "name": "California"},
                "provenance": "https://example.org/source1",
            },
            "friends": [
                {
                    "value": {"@id": "http://example.org/person/bob", "@type": "Person", "name": "Bob"},
                    "provenance": "https://example.org/source1",
                }
            ],
        }
        return schema


# JSON-LD models
class JSONLDDocument(BaseModel):
    context: dict[str, Any] = Field(..., alias="@context")
    graph: list[GraphNode] = Field(..., alias="@graph")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "@context": {
                    "@vocab": "http://localhost:5000/schema/local/",
                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                },
                "@graph": [
                    {
                        "@id": "node1",
                        "@type": "Person",
                        "name": {"@value": "Alice"},
                        "aliases": [{"@value": "Al"}],
                        "home": {"@id": "place:geoId/06", "@type": ["State"]},
                    }
                ],
            }
        },
    )
