import json
from typing import List
from datacommons.tools.mcf.mcf import PropertyValue, Node

def mcf_node_to_jsonld(node: Node, compact = False) -> dict:
    # Build literal properties
    props = {
        key: [{"@type": pv.type, "@value": f"{pv.namespace}:{pv.value}" if pv.type == "reference" else pv.value} for pv in values]
        for key, values in node.properties.items()
    }
    
    # Assemble node
    node_dict = {"@id": node.node_id}
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
                properties[key].append({
                    "@type": pv.type,
                    "@value": pv.get_value()
                })
    
    node_dict["properties"] = properties
    node_dict["outbound"] = outbound_edges

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
      
      node_dict["properties"] = properties
      node_dict["outbound"] = outbound_edges
    return node_dict

def build_jsonld_document(nodes: List[Node], compact = False) -> dict:
    context = {
        "@version": 1.1,
        "@vocab": "https://schema.org/",
        "ex": "http://example.org/vocab/",
        "properties": {"@id": "ex:properties", "@nest": "@nest"},
        "outbound": {"@id": "ex:outbound", "@nest": "@nest"}
    }
    graph = [mcf_node_to_jsonld(n, compact) for n in nodes]
    return {"@context": context, "@graph": graph}
