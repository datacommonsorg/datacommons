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

import pytest
from io import StringIO
from datacommons_schema.models.jsonld import GraphNode
from datacommons_schema.services.schema_service import (
    SchemaService,
    ValidationError,
)

@pytest.fixture
def schema_service():
    service = SchemaService()
    schema = """
    {
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
    }
    """
    service.load_schema(StringIO(schema))
    return service

def test_validate_node_with_valid_node(schema_service: SchemaService):
    node = GraphNode(**{"@id": "test", "@type": "Person", "name": "test"})
    schema_service.validate_node(node)

def test_validate_node_with_invalid_type(schema_service: SchemaService):
    node = GraphNode(**{"@id": "test", "@type": "InvalidType", "name": "test"})
    with pytest.raises(ValidationError):
        schema_service.validate_node(node)

def test_validate_node_with_invalid_property(schema_service: SchemaService):
    node = GraphNode(**{"@id": "test", "@type": "Person", "invalid_prop": "test"})
    with pytest.raises(ValidationError):
        schema_service.validate_node(node)
