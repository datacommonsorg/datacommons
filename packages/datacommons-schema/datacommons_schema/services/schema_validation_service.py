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
from typing import List, Dict, Set, Any, Union, Optional
from pydantic import BaseModel, Field, ConfigDict
from rdflib import Graph, URIRef, Literal, RDF, RDFS, XSD

class SchemaError(BaseModel):
    subject: str      # The property causing the issue (e.g., local:name)
    issue: str        # e.g., "Dangling Reference"
    message: str      # e.g., "Refers to class local:Ghost which is undefined"

class SchemaReport(BaseModel):
    is_valid: bool
    errors: List[SchemaError]

class ValidationError(BaseModel):
    """Represents a single issue found in the data."""
    subject: str
    predicate: str
    object: str
    message: str
    rule_type: str = Field(..., description="The type of rule violated (e.g., 'Domain', 'Range', 'Undefined Property')")

class ValidationReport(BaseModel):
    """The final output of a validation run."""
    is_valid: bool
    error_count: int
    errors: List[ValidationError] = []

class SchemaDefinition(BaseModel):
    """
    Internal storage for the rules extracted from the RDFS schema.
    We allow arbitrary types to store rdflib objects (URIRef) directly for performance.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    classes: Set[URIRef] = Field(default_factory=set)
    properties: Set[URIRef] = Field(default_factory=set)
    domains: Dict[URIRef, URIRef] = Field(default_factory=dict) # Property -> Class
    ranges: Dict[URIRef, URIRef] = Field(default_factory=dict)  # Property -> Class/Datatype

class SchemaValidationService:
    """
    A strict JSON-LD RDFS-based validator for ensuring data conformity against a defined schema.

    This validator operates on a 'Closed World' assumption for domain and range checks:
    any Class or Property referenced in the data must be explicitly defined in the provided schema.

    Attributes:
        schema_graph (rdflib.Graph): The raw RDF graph of the schema.
        rules (SchemaDefinition): An internal lookup table of classes, properties, domains, and ranges.

    Examples:
        >>> schema = {
        ...     "@context": {"local": "http://example.org/", "rdfs": "http://www.w3.org/2000/01/rdf-schema#"},
        ...     "@graph": [
        ...         {"@id": "local:Person", "@type": "rdfs:Class"},
        ...         {"@id": "local:name", "@type": "rdf:Property", "rdfs:domain": {"@id": "local:Person"}}
        ...     ]
        ... }
        >>> validator = SchemaValidationService(schema)
        >>> report = validator.validate_schema_integrity()
        >>> print(report.is_valid)
        True
    """

    def __init__(self, graph: Graph):
        """
        Initializes the validator by parsing the schema and extracting validation rules.

        Args:
            graph (Graph): The schema definition.

        Example:

        >>> graph = Graph()
        >>> graph.parse(data="""
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
        """, format="json-ld")
        >>> validator = SchemaValidator(graph)

        Raises:
            rdflib.plugin.PluginException: If the input format is not recognized as JSON-LD.
        """
        self.schema_graph = graph
        self.rules = self._extract_rules()

    def _extract_rules(self) -> SchemaDefinition:
        """
        Compiles high-level validation rules from the raw schema graph.

        This method scans the schema for:
        1. All defined `rdfs:Class` entities.
        2. All `rdf:Property` entities.
        3. `rdfs:domain` and `rdfs:range` constraints for each property.

        Returns:
            SchemaDefinition: A frozen dataclass containing sets of valid classes/properties
            and dictionaries mapping properties to their domain/range constraints.
        """
        rules = SchemaDefinition()

        # 1. Extract Classes
        for s, _, _ in self.schema_graph.triples((None, RDF.type, RDFS.Class)):
            rules.classes.add(s)

        # 2. Extract Properties and their Domain/Range
        for s, _, _ in self.schema_graph.triples((None, RDF.type, RDF.Property)):
            rules.properties.add(s)
            
            # Domain (Subject Type)
            domain = self.schema_graph.value(s, RDFS.domain)
            if domain:
                rules.domains[s] = domain
            
            # Range (Object Type)
            range_type = self.schema_graph.value(s, RDFS.range)
            if range_type:
                rules.ranges[s] = range_type
                
        return rules
    
    def validate_schema_integrity(self, context_classes: Optional[Set[URIRef]] = None) -> SchemaReport:
        """
        Performs a self-check on the schema to identify internal inconsistencies.

        This method detects 'Dangling References'—instances where a property defines a 
        domain or range that points to a class not defined within the schema itself 
        (or standard XSD types). This enforces a strict schema definition where all 
        dependencies must be present.

        Args:
            context_classes (Optional[Set[URIRef]]): A set of classes known to exist externally 
                (e.g., in the main Knowledge Graph). This allows validates partial schema updates 
                that depend on existing classes.

        Returns:
            SchemaReport: A Pydantic model containing a boolean validity flag and a list 
            of specific `SchemaError` objects if inconsistencies are found.

        Examples:
            >>> # Schema referencing undefined 'local:Ghost' class
            >>> bad_schema = {
            ...     "@graph": [{
            ...         "@id": "local:prop", 
            ...         "@type": "rdf:Property", 
            ...         "rdfs:domain": {"@id": "local:Ghost"}
            ...     }]
            ... }
            >>> v = SchemaValidationService(bad_schema)
            >>> report = v.validate_schema_integrity()
            >>> print(report.errors[0].issue)
            Undefined Domain Target
        """
        errors = []
        
        # Standard XSD types we always accept as valid ranges
        known_types = {
            XSD.string, XSD.integer, XSD.float, XSD.boolean, 
            XSD.date, XSD.dateTime, RDFS.Literal
        }
        
        # Combine internal classes with external context
        valid_classes = self.rules.classes.copy()
        if context_classes:
            valid_classes.update(context_classes)

        # 1. Check Domains
        # Every domain target must be a known Class in our schema
        for prop, domain_class in self.rules.domains.items():
            if domain_class not in valid_classes:
                errors.append(SchemaError(
                    subject=str(prop),
                    issue="Undefined Domain Target",
                    message=f"Property defines domain as <{domain_class}>, but that Class is not defined."
                ))

        # 2. Check Ranges
        # Every range target must be a known Class OR a standard XSD type
        for prop, range_target in self.rules.ranges.items():
            is_defined_class = range_target in valid_classes
            is_standard_type = range_target in known_types
            
            if not (is_defined_class or is_standard_type):
                errors.append(SchemaError(
                    subject=str(prop),
                    issue="Undefined Range Target",
                    message=f"Property defines range as <{range_target}>, but that is not a defined Class or XSD type."
                ))

        # 3. Check for Malformed URIs (Unexpanded CURIEs)
        # If a prefix is missing in @context, terms like "rdf:Property" are parsed as URIs with scheme "rdf".
        # We enforce that all URIs must use standard schemes (http, https, urn).
        from urllib.parse import urlparse
        
        allowed_schemes = {"http", "https", "urn"}
        
        # We scan all unique URIs in the graph (subjects, predicates, objects)
        all_uris = set()
        for s, p, o in self.schema_graph:
            if isinstance(s, URIRef): all_uris.add(s)
            if isinstance(p, URIRef): all_uris.add(p)
            if isinstance(o, URIRef): all_uris.add(o)
            
        for uri in all_uris:
            parsed = urlparse(str(uri))
            if parsed.scheme not in allowed_schemes:
                errors.append(SchemaError(
                    subject=str(uri),
                    issue="Malformed URI / Missing Prefix",
                    message=f"Term <{uri}> has unknown scheme '{parsed.scheme}'. This usually means a prefix (like '{parsed.scheme}:') is missing from @context."
                ))

        # 4. Check for Unknown RDF/RDFS Terms
        # Ensure that we are not using made-up terms in the RDF/RDFS namespaces (e.g. rdf:Propertyzzz)
        rdf_ns = str(RDF)
        rdfs_ns = str(RDFS)
        
        # Strict allowlist for this validator
        valid_rdf_terms = {
            "type", "Property", "List", "first", "rest", "nil", "Statement", "subject", "predicate", "object", "value"
        }
        valid_rdfs_terms = {
            "Class", "subClassOf", "subPropertyOf", "domain", "range", "label", "comment", 
            "seeAlso", "isDefinedBy", "Literal", "Datatype", "Resource", "Container", "Member"
        }
        
        for uri in all_uris:
            uri_str = str(uri)
            if uri_str.startswith(rdf_ns):
                term = uri_str[len(rdf_ns):]
                if term not in valid_rdf_terms:
                     errors.append(SchemaError(
                        subject=str(uri),
                        issue="Unknown RDF Term",
                        message=f"Term <{uri}> is not a recognized RDF term."
                    ))
            elif uri_str.startswith(rdfs_ns):
                term = uri_str[len(rdfs_ns):]
                if term not in valid_rdfs_terms:
                     errors.append(SchemaError(
                        subject=str(uri),
                        issue="Unknown RDFS Term",
                        message=f"Term <{uri}> is not a recognized RDFS term."
                    ))

        # 5. Check for Unknown XSD Terms
        xsd_ns = str(XSD)
        valid_xsd_terms = {
            "string", "boolean", "decimal", "float", "double", "duration", "dateTime", "time", "date", 
            "gYearMonth", "gYear", "gMonthDay", "gDay", "gMonth", "hexBinary", "base64Binary", 
            "anyURI", "QName", "NOTATION", "normalizedString", "token", "language", "NMTOKEN", 
            "NMTOKENS", "Name", "NCName", "ID", "IDREF", "IDREFS", "ENTITY", "ENTITIES", 
            "integer", "nonPositiveInteger", "negativeInteger", "long", "int", "short", "byte", 
            "nonNegativeInteger", "unsignedLong", "unsignedInt", "unsignedShort", "unsignedByte", 
            "positiveInteger", "yearMonthDuration", "dayTimeDuration", "dateTimeStamp"
        }

        for uri in all_uris:
            uri_str = str(uri)
            if uri_str.startswith(xsd_ns):
                term = uri_str[len(xsd_ns):]
                if term not in valid_xsd_terms:
                     errors.append(SchemaError(
                        subject=str(uri),
                        issue="Unknown XSD Term",
                        message=f"Term <{uri}> is not a recognized XSD term."
                    ))

        return SchemaReport(
            is_valid=(len(errors) == 0),
            errors=errors
        )

    def validate(self, data_graph: Graph, context_graph: Optional[Graph] = None) -> ValidationReport:
        """
        Validates a data file against the loaded schema rules.

        The validation logic checks three primary conditions for every triple in the data:
        1. **Property Existence:** Is the predicate defined in the schema?
        2. **Domain Compliance:** Does the subject have the `rdf:type` required by the predicate's domain?
        3. **Range Compliance:** Does the object have the `rdf:type` (or datatype) required by the predicate's range?

        Note: RDFS descriptive properties (label, comment) are explicitly ignored during validation.

        Args:
            data_input (Union[str, Dict[str, Any], Graph]): The data to validate, provided as a 
                JSON-LD string, dictionary, or rdflib.Graph.
            context_graph (Optional[Graph]): An optional graph containing the existing Knowledge Graph 
                context. This allows verifying types/existence of nodes not in the new data batch.

        Returns:
            ValidationReport: A detailed Pydantic report containing the overall validity status,
            error counts, and a list of specific `ValidationError` objects for any violations found.
        """
        errors = []

        def has_type(resource, type_uri):
            # Check existence of (resource, rdf:type, type_uri) in:
            # 1. The new data being added
            # 2. The existing Knowledge Graph context (if provided)
            # 3. The Schema itself (less likely for instances, but possible for meta-modeling)
            
            if (resource, RDF.type, type_uri) in data_graph:
                return True
            if context_graph and (resource, RDF.type, type_uri) in context_graph:
                return True
            if (resource, RDF.type, type_uri) in self.schema_graph:
                return True
            return False

        for s, p, o in data_graph:
            # Skip validation for RDFS/RDF/XSD definition terms within the data
            # This allows bootstrapping schema definitions without explicitly defining rdfs:domain etc.
            p_str = str(p)
            if p_str.startswith(str(RDF)) or p_str.startswith(str(RDFS)) or p_str.startswith(str(XSD)):
                continue

            # Check 1: Is the Property Defined?
            if p not in self.rules.properties:
                errors.append(ValidationError(
                    subject=str(s), predicate=str(p), object=str(o),
                    message="Property not defined in schema.",
                    rule_type="Undefined Property"
                ))
                continue

            # Check 2: Domain Validation
            if p in self.rules.domains:
                required_domain = self.rules.domains[p]
                # Query: Does Subject 's' have type 'required_domain'?
                if not has_type(s, required_domain):
                    errors.append(ValidationError(
                        subject=str(s), predicate=str(p), object=str(o),
                        message=f"Subject must be of type <{required_domain}>",
                        rule_type="Domain Violation"
                    ))

            # Check 3: Range Validation
            if p in self.rules.ranges:
                required_range = self.rules.ranges[p]
                
                # Case A: Literal
                if isinstance(o, Literal):
                    # If the range is a class URI, a literal is invalid.
                    if not (str(required_range).startswith(str(XSD)) or required_range == RDFS.Literal):
                        errors.append(ValidationError(
                            subject=str(s), predicate=str(p), object=str(o),
                            message=f"Object must be a resource of type <{required_range}>, but a literal was found.",
                            rule_type="Range Violation"
                        ))
                        continue

                    # An untyped literal is compatible with xsd:string. Otherwise, datatypes must match.
                    effective_datatype = o.datatype or XSD.string
                    if effective_datatype != required_range:
                        errors.append(ValidationError(
                            subject=str(s), predicate=str(p), object=str(o),
                            message=f"Literal has datatype <{effective_datatype}> but range requires <{required_range}>.",
                            rule_type="Range Violation"
                        ))

                # Case B: Resource (URI)
                elif isinstance(o, URIRef):
                    # Query: Does Object 'o' have type 'required_range'?
                    if not has_type(o, required_range):
                        errors.append(ValidationError(
                            subject=str(s), predicate=str(p), object=str(o),
                            message=f"Object must be of type <{required_range}>",
                            rule_type="Range Violation"
                        ))

        return ValidationReport(
            is_valid=(len(errors) == 0),
            error_count=len(errors),
            errors=errors
        )