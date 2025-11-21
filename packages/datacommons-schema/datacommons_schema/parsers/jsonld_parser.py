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
from typing import IO

from datacommons_schema.models.primitives import rdf, shacl


class JSONLDParseError(Exception):
    """Raised when JSON-LD parsing fails"""


def parse_jsonld(stream: IO[str]) -> list[rdf.RDFResource]:
    """Parse a JSON-LD file and return a list of RDFResource objects.

    Args:
        stream: A file-like object containing JSON-LD content.

    Returns:
        A list of RDFResource objects.

    Raises:
        JSONLDParseError: If the JSON-LD content is invalid.
    """
    try:
        data = json.load(stream)
    except json.JSONDecodeError as e:
        raise JSONLDParseError(f"Invalid JSON: {e}") from e

    if "@graph" not in data:
        raise JSONLDParseError("Missing '@graph' key in JSON-LD file.")

    context = data.get("@context", {})

    def expand_uri(uri: str) -> str:
        """Expand a URI using the context."""
        if not isinstance(uri, str):
            return uri
        for prefix, namespace in context.items():
            if uri.startswith(f"{prefix}:"):
                return uri.replace(f"{prefix}:", namespace, 1)
        return uri

    resources = []
    for node in data["@graph"]:
        node_type = expand_uri(node.get("@type"))
        if node_type == f"{rdf.RDFS_NS}Class":
            resources.append(rdf.RDFSClass(**node))
        elif node_type == f"{rdf.RDF_NS}Property":
            resources.append(rdf.RDFProperty(**node))
        elif node_type == f"{shacl.SHACL_NS}NodeShape":
            resources.append(shacl.SHACLNodeShape(**node))
        else:
            # For now, we only support RDFSClass, RDFProperty, and SHACLNodeShape
            continue

    return resources
