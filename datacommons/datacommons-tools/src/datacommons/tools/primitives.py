"""Core schema primitives for the Data Commons schema system."""

from enum import Enum, auto
from typing import Dict, List, Set, TypedDict


class PrimitiveType(str, Enum):
    """Core primitive types from schema.org."""
    THING = "Thing"
    CLASS = "Class"
    DATATYPE = "DataType"
    PROPERTY = "Property"


class DataType(str, Enum):
    """Basic data types."""
    TEXT = "Text"
    NUMBER = "Number"
    BOOLEAN = "Boolean"
    DATE = "Date"
    DATETIME = "DateTime"
    URL = "URL"


class RelationshipType(str, Enum):
    """Relationship types for properties."""
    DOMAIN_INCLUDES = "domainIncludes"
    RANGE_INCLUDES = "rangeIncludes"


class PropertyDefinition(TypedDict):
    """Structure for property definitions."""
    id: str
    type: str
    domain_includes: List[str]
    range_includes: List[str]
    description: str


# Core primitive types that can be used in JSON-LD
PRIMITIVE_TYPES: Set[str] = {t.value for t in PrimitiveType}

# Valid data types
DATA_TYPES: Set[str] = {t.value for t in DataType}

# Valid relationship types
RELATIONSHIP_TYPES: Set[str] = {t.value for t in RelationshipType}

# Required fields for each primitive type
REQUIRED_FIELDS: Dict[str, Set[str]] = {
    PrimitiveType.THING.value: {"id", "type"},
    PrimitiveType.CLASS.value: {"id", "type"},
    PrimitiveType.DATATYPE.value: {"id", "type"},
    PrimitiveType.PROPERTY.value: {"id", "type", "domain_includes", "range_includes"}
}

# Optional fields for each primitive type
OPTIONAL_FIELDS: Dict[str, Set[str]] = {
    PrimitiveType.THING.value: {"description"},
    PrimitiveType.CLASS.value: {"description"},
    PrimitiveType.DATATYPE.value: {"description"},
    PrimitiveType.PROPERTY.value: {"description"}
}
