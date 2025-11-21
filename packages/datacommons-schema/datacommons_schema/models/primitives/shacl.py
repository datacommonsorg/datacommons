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

SHACL_NS = "http://www.w3.org/ns/shacl#"


class SHACLProperty(BaseModel):
    path: str = Field(..., alias=f"{SHACL_NS}path")
    datatype: str | None = Field(None, alias=f"{SHACL_NS}datatype")
    node_kind: str | None = Field(None, alias=f"{SHACL_NS}nodeKind")
    min_count: int | None = Field(None, alias=f"{SHACL_NS}minCount")
    max_count: int | None = Field(None, alias=f"{SHACL_NS}maxCount")


class SHACLNodeShape(BaseModel):
    id: str = Field(..., alias="@id")
    type: str = Field(default=f"{SHACL_NS}NodeShape", alias="@type")
    target_class: str | None = Field(None, alias=f"{SHACL_NS}targetClass")
    properties: list[SHACLProperty] | None = Field(None, alias=f"{SHACL_NS}property")
