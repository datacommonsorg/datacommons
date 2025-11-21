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

from pydantic import BaseModel, Field

# RDF, RDFS, and XSD Namespaces
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"


class RDFResource(BaseModel):
    id: str = Field(..., alias="@id")


class RDFSClass(RDFResource):
    type: str = Field(default=f"{RDFS_NS}Class", alias="@type")
    label: str | None = Field(None, alias=f"{RDFS_NS}label")
    comment: str | None = Field(None, alias=f"{RDFS_NS}comment")
    subclass_of: list[str] | None = Field(None, alias=f"{RDFS_NS}subClassOf")


class RDFProperty(RDFResource):
    type: str = Field(default=f"{RDF_NS}Property", alias="@type")
    label: str | None = Field(None, alias=f"{RDFS_NS}label")
    comment: str | None = Field(None, alias=f"{RDFS_NS}comment")
    domain: list[str] | None = Field(None, alias=f"{RDFS_NS}domain")
    range: list[str] | None = Field(None, alias=f"{RDFS_NS}range")


class XSDDatatype(RDFResource):
    type: str = Field(default=f"{RDFS_NS}Datatype", alias="@type")
    label: str | None = Field(None, alias=f"{RDFS_NS}label")
