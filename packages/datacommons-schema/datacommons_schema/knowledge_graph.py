from typing import List, Dict, Union, Optional
from rdflib import Graph
import json

from datacommons_schema.services.schema_validation_service import SchemaValidationService, SchemaReport, ValidationReport, ValidationError


class KnowledgeGraph:
    """
    An in-memory Knowledge Graph using rdflib.
    """
    def __init__(self, namespace: str, default_prefix: str = "ex"):
        self.namespace = namespace
        self.default_prefix = default_prefix
        self._graph = Graph()
        # Bind the default prefix to the namespace
        self._graph.bind(self.default_prefix, self.namespace)

    def validate(self, nodes: Union[Dict, List[Dict]]) -> ValidationReport:
        # 1. Parse new nodes into a temp graph
        temp_graph = self._load_graph(nodes)
        
        # 2. extract existing rules to serve as context
        # Note: In a real high-perf scenario, we would cache the 'rules' 
        # instead of re-extracting them from self._graph every time.
        main_validator = SchemaValidationService(self._graph)
        
        # 3. Check Schema Integrity of NEW nodes
        # Use existing classes as context so we don't flag references to existing classes as "Undefined"
        temp_validator = SchemaValidationService(temp_graph)
        schema_report = temp_validator.validate_schema_integrity(context_classes=main_validator.rules.classes)
        
        if not schema_report.is_valid:
            # Map schema errors to validation errors
            schem_errors = []
            for se in schema_report.errors:
                schem_errors.append(ValidationError(
                    subject=se.subject,
                    predicate="N/A",
                    object="N/A",
                    message=f"Schema Integrity Error: {se.issue} - {se.message}",
                    rule_type="SchemaIntegrity"
                ))
            return ValidationReport(
                is_valid=False,
                error_count=len(schem_errors),
                errors=schem_errors
            )
        
        # 4. Check Data Validation
        # Validates 'temp_graph' against 'self._graph' rules and context
        return main_validator.validate(temp_graph, context_graph=self._graph)

    def add(self, nodes: Union[Dict, List[Dict]]) -> None:
        report = self.validate(nodes)
        if not report.is_valid:
            error_msgs = "\n".join([f"{e.subject}: {e.message}" for e in report.errors])
            raise ValueError(f"Cannot add invalid nodes:\n{error_msgs}")
        
        # If valid, merge
        temp_graph = self._load_graph(nodes)
        self._graph += temp_graph

    def _load_graph(self, jsonld_input: Union[Dict, List[Dict], str]) -> Graph:
        g = Graph()
        if isinstance(jsonld_input, (dict, list)):
            data = json.dumps(jsonld_input)
        else:
            data = jsonld_input
        g.parse(data=data, format="json-ld")
        return g
