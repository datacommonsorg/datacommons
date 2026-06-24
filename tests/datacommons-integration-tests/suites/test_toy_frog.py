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


def test_observation_frog(target_url, api_client):
    path = "/core/api/v2/observation?select=variable&select=entity&select=date&select=value&variable.dcids=number_of_frogs&entity.dcids=country/USA&entity.dcids=country/CAN"
    resp = api_client(target_url, path, headers={"X-Use-Multi-Entity-Schema": "true"})

    by_var = resp.get("byVariable", {})
    assert "number_of_frogs" in by_var, (
        f"Expected 'number_of_frogs' variable in response: {resp}"
    )
    by_entity = by_var["number_of_frogs"].get("byEntity", {})
    for entity in ["country/USA", "country/CAN"]:
        assert entity in by_entity, f"Missing entity '{entity}' in response"
        facets = by_entity[entity].get("orderedFacets", [])
        assert len(facets) > 0
        assert len(facets[0].get("observations", [])) > 0


def test_resolve_frogs(target_url, api_client):
    path = "/core/api/v2/resolve?nodes=frogs&resolver=indicator&target=custom_only"
    resp = api_client(target_url, path)

    entities = resp.get("entities", [])
    assert len(entities) > 0
    node_res = entities[0]
    assert node_res.get("node") == "frogs"
    candidates = node_res.get("candidates", [])
    assert len(candidates) > 0
    has_candidate = any(
        c.get("dcid") in ("number_of_frogs", "Count_Frog_Green") for c in candidates
    )
    assert has_candidate, (
        f"Expected candidate 'number_of_frogs' or 'Count_Frog_Green', got: {candidates}"
    )
