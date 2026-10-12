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


import pytest

from tests.integration.core.config_schema import ExpectedTargetSpec, NodeQuerySpec
from tests.integration.core.target import DCPTarget


class TestV2Node:
    """Validates Node properties and graph edge inspection via datacommons-client."""

    def test_node_fetch_expression(
        self,
        seeded_testbed,
        dc_client,
        dcp_target: DCPTarget,
        node_query_spec: NodeQuerySpec | None,
    ):
        """Verifies dc_client.node.fetch for declared node and expression."""
        if not node_query_spec:
            pytest.skip(
                "No node queries defined in manifest or serving_api stage disabled."
            )

        res = dc_client.node.fetch(
            node_dcids=[node_query_spec.node_dcid],
            expression=node_query_spec.expression,
        )
        assert res is not None, (
            f"Expected non-null response for node '{node_query_spec.node_dcid}'"
        )

        if node_query_spec.expected_values:
            text_repr = str(res)
            matched = any(val in text_repr for val in node_query_spec.expected_values)
            assert matched, (
                f"Node '{node_query_spec.node_dcid}' with expr '{node_query_spec.expression}' "
                f"did not contain any of {node_query_spec.expected_values}. Response: {text_repr[:300]}"
            )

        if node_query_spec.expected_targets:
            targets = node_query_spec.expected_targets
            if dcp_target.instance_name == "emulated":
                # The emulated stack has no Base DC to hydrate remote targets from.
                targets = [t for t in targets if not t.requires_base_dc]
                if not targets:
                    pytest.skip(
                        "Targets require Base DC, which the emulated stack lacks."
                    )
            _assert_expected_targets(res, node_query_spec, targets)


def _arc_property(expression: str) -> str:
    """Returns the property of a single-hop outgoing expression like '->memberOf'."""
    message = f"expected_targets supports single-hop '->property' expressions only, got '{expression}'"
    assert expression.startswith("->"), message
    prop = expression.removeprefix("->")
    assert prop, message
    assert not any(op in prop for op in ("->", "<-", "[", "{", ",")), message
    return prop


def _assert_expected_targets(
    res, spec: NodeQuerySpec, expected_targets: list[ExpectedTargetSpec]
) -> None:
    """Asserts arc targets by field; substring checks can't tell a hydrated node from a stub."""
    prop = _arc_property(spec.expression)
    targets = {n.dcid: n for n in res.extract_connected_nodes(spec.node_dcid, prop)}
    for expected in expected_targets:
        label = f"'{spec.node_dcid} {spec.expression}' target '{expected.dcid}'"
        node = targets.get(expected.dcid)
        assert node is not None, f"{label} not returned. Got: {sorted(targets)}"
        assert node.name == expected.name, (
            f"{label} name is {node.name!r}, expected {expected.name!r}"
        )
        types = list(node.types or [])
        missing = set(expected.types) - set(types)
        assert not missing, (
            f"{label} missing types {sorted(missing)}; got {types}. Remote targets that "
            "Mixer did not hydrate from Base DC come back as ['Thing']."
        )
