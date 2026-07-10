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


def test_v2_multi_entity_observation_sdg(target_url, api_client):
    """Test 1: V2 Multi-entity Observation (SDG)"""
    path = "/core/api/v2/observation?select=variable&select=entity&select=date&select=value&variable.dcids=undata/sdg/IT_MOB_OWN.SEX--_T&entity.dcids=country/IND&entity.dcids=country/USA"
    # Just verify it returns 200 OK
    api_client(target_url, path, headers={"X-Use-Multi-Entity-Schema": "true"})


def test_verify_wages_data(target_url, api_client):
    """Test 2: Verify Wages Data (Custom Data)"""
    path = "/core/api/v2/observation?select=variable&select=entity&select=date&select=value&variable.dcids=average_annual_wage&entity.dcids=country/USA&entity.dcids=country/CAN"
    resp = api_client(target_url, path, headers={"X-Use-Multi-Entity-Schema": "true"})

    by_var = resp.get("byVariable", {})
    assert "average_annual_wage" in by_var, (
        f"Expected variable 'average_annual_wage' in response, got: {resp}"
    )

    by_entity = by_var["average_annual_wage"].get("byEntity", {})
    assert "country/USA" in by_entity, (
        f"Expected entity 'country/USA' in response, got: {by_entity.keys()}"
    )
    assert "country/CAN" in by_entity, (
        f"Expected entity 'country/CAN' in response, got: {by_entity.keys()}"
    )

    for entity_dcid, entity_data in by_entity.items():
        facets = entity_data.get("orderedFacets", [])
        assert facets, (
            f"Expected orderedFacets list for {entity_dcid}, got: {entity_data}"
        )
        observations = facets[0].get("observations", [])
        assert observations, (
            f"Expected observations list for {entity_dcid}, got: {entity_data}"
        )


def test_v2_bulk_variable_group_info_unconstrained(target_url, api_client):
    """Test 3a: V2 Bulk Variable Group Info (Unconstrained)"""
    path = "/core/api/v2/bulk/info/variable-group?nodes=dc/g/undata/SDG_1.5.1"
    api_client(target_url, path, headers={"X-Use-Multi-Entity-Schema": "true"})


def test_v2_bulk_variable_group_info_constrained_usa(target_url, api_client):
    """Test 3b: V2 Bulk Variable Group Info (Constrained by USA)"""
    path = "/core/api/v2/bulk/info/variable-group?nodes=dc/g/undata/SDG_1.5.1&constrained_entities=country/USA"
    api_client(target_url, path, headers={"X-Use-Multi-Entity-Schema": "true"})


def test_v2_bulk_variable_group_info_constrained_vat(target_url, api_client):
    """Test 3c: V2 Bulk Variable Group Info (Constrained by VAT)"""
    path = "/core/api/v2/bulk/info/variable-group?nodes=dc/g/undata/SDG_1.5.1&constrained_entities=country/VAT"
    api_client(target_url, path, headers={"X-Use-Multi-Entity-Schema": "true"})


def test_v2_resolve_indicator_food_waste(target_url, api_client):
    """Test 4: V2 Resolve - Indicator resolver (Food Waste)"""
    path = (
        "/core/api/v2/resolve?nodes=food%20waste&resolver=indicator&target=custom_only"
    )
    api_client(target_url, path)


def test_v2_resolve_indicator_wages(target_url, api_client):
    """Test 5: V2 Resolve - Indicator resolver (Wages)"""
    path = "/core/api/v2/resolve?nodes=wages&resolver=indicator&target=custom_only"
    resp = api_client(target_url, path)

    entities = resp.get("entities", [])
    assert entities, f"Expected non-empty 'entities' list, got: {resp}"

    node_res = entities[0]
    assert node_res.get("node") == "wages", (
        f"Expected resolved node for 'wages', got: {node_res}"
    )

    candidates = node_res.get("candidates", [])
    assert candidates, f"Expected resolved candidates for 'wages', got: {node_res}"

    has_sv = any(
        c.get("dcid") in ("average_annual_wage", "gender_wage_gap") for c in candidates
    )
    assert has_sv, (
        f"Expected resolved candidate to match 'average_annual_wage' or 'gender_wage_gap', got: {candidates}"
    )
