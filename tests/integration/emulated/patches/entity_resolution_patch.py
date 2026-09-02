# Copyright 2026 Google LLC.
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

"""Mocks base Data Commons entity resolution during local ingestion preprocessing.

Provides local dictionary resolution for standard entities (e.g. country/USA, country/CAN)
so the ingestion data-processor does not make external network calls to the public API.
"""

import sys
from pathlib import Path

try:
    for p in ["/workspace/import/simple", str(Path.cwd())]:
        if p not in sys.path:
            sys.path.append(p)

    from util import dc_client

    HAS_DC_CLIENT = True
except (ImportError, ModuleNotFoundError):
    HAS_DC_CLIENT = False

KNOWN_PLACES = {
    "country/USA": "United States of America",
    "country/CAN": "Canada",
    "country/MEX": "Mexico",
    "country/GBR": "United Kingdom",
    "country/FRA": "France",
    "country/DEU": "Germany",
    "country/JPN": "Japan",
}


def _get_entity_name(dcid: str) -> str:
    if dcid in KNOWN_PLACES:
        return KNOWN_PLACES[dcid]
    if dcid.startswith("country/"):
        return dcid.split("/", 1)[1].replace("_", " ").title()
    return dcid


def _get_entity_type(dcid: str) -> str:
    if dcid.startswith("country/"):
        return "Country"
    if dcid.startswith("geoId/"):
        return "State"
    return ""


if HAS_DC_CLIENT:

    def patched_get_property_of_entities(entities, property_name):
        if "name" in property_name:
            return {e: _get_entity_name(e) for e in entities}
        if "typeOf" in property_name:
            return {e: _get_entity_type(e) or e for e in entities}
        return {e: e for e in entities}

    def patched_resolve_entities(
        entities, entity_type=None, property_name="description"
    ):
        return {e: _get_entity_name(e) for e in entities}

    def patched_get_entities_of_type(entity_type, next_token=None):
        return {}, ""

    def patched_resolve_entity_type(entity_dcids):
        return _get_entity_type(entity_dcids[0]) if len(entity_dcids) == 1 else ""

    dc_client.get_property_of_entities = patched_get_property_of_entities
    dc_client.resolve_entities = patched_resolve_entities
    dc_client.get_entities_of_type = patched_get_entities_of_type
    dc_client.resolve_entity_type = patched_resolve_entity_type
