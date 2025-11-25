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

from datacommons_schema.models.jsonld import GraphNode, JSONLDDocument
from datacommons_schema.models.mcf import McfNode


def mcf_node_to_jsonld(node: McfNode, *, compact: bool = False) -> GraphNode:
    # Assemble node
    graph_node = GraphNode(**{"@id": node.node_id})
    # Split properties into literal properties and outbound edges
    properties = {}
    outbound_edges = {}

    for key, values in node.properties.items():
        for pv in values:
            if pv.type == "reference":
                if key not in outbound_edges:
                    outbound_edges[key] = []
                outbound_edges[key].append({"@id": f"{pv.namespace}:{pv.value}"})
            else:
                if key not in properties:
                    properties[key] = []
                properties[key].append({"@type": pv.type, "@value": pv.get_value()})

    graph_node.properties = properties
    graph_node.outbound = outbound_edges

    # If compact mode requested, simplify the property values
    if compact:
        properties = {}
        outbound_edges = {}

        for key, values in node.properties.items():
            for pv in values:
                if pv.type == "reference":
                    if key not in outbound_edges:
                        outbound_edges[key] = []
                    outbound_edges[key].append(f"{pv.namespace}:{pv.value}")
                else:
                    if key not in properties:
                        properties[key] = []
                    properties[key].append(pv.get_value())

        graph_node.properties = properties
        graph_node.outbound = outbound_edges
    return graph_node


def mcf_nodes_to_jsonld(
    nodes: list[McfNode], *, compact: bool = False
) -> JSONLDDocument:
    context = {
        "@version": 1.1,
        "@vocab": "https://schema.org/",
        "ex": "http://example.org/vocab/",
        "properties": {"@id": "ex:properties", "@nest": "@nest"},
        "outbound": {"@id": "ex:outbound", "@nest": "@nest"},
    }
    graph_nodes = [mcf_node_to_jsonld(n, compact=compact) for n in nodes]
    return JSONLDDocument(**{"@context": context, "@graph": graph_nodes})
