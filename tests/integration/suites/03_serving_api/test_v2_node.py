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

from tests.integration.core.config_schema import NodeQuerySpec, TestManifest
from tests.integration.core.dataset_introspection import declared_mcf_dcids


class TestV2Node:
    """Validates Node properties and graph edge inspection via datacommons-client."""

    def test_node_fetch_expression(
        self,
        seeded_testbed,
        dc_client,
        test_manifest: TestManifest,
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
            declared = declared_mcf_dcids(test_manifest.ingestion.dataset_dirs)
            _assert_expected_targets(res, node_query_spec, declared)


# Type Mixer assigns to arc targets that have no row in local Spanner and were
# not hydrated from Base DC (see mixer UnresolvedNodeProcessor).
_UNRESOLVED_TYPE = "Thing"


def _arc_property(expression: str) -> str:
    """Returns the property of a single-hop outgoing expression like '->memberOf'."""
    message = f"expected_targets supports single-hop '->property' expressions only, got '{expression}'"
    assert expression.startswith("->"), message
    prop = expression.removeprefix("->")
    assert prop.isidentifier(), message
    return prop


def _assert_expected_targets(
    res, spec: NodeQuerySpec, declared_dcids: set[str]
) -> None:
    prop = _arc_property(spec.expression)
    targets = {n.dcid: n for n in res.extract_connected_nodes(spec.node_dcid, prop)}
    for expected in spec.expected_targets:
        label = f"'{spec.node_dcid} {spec.expression}' target '{expected.dcid}' ({expected.locality})"

        # Guard the spec itself: a "remote" target declared in the dataset would
        # resolve from Spanner and never exercise Base DC hydration.
        assert expected.locality in ("local", "remote"), (
            f"{label}: locality must be 'local' or 'remote'"
        )
        is_declared = expected.dcid in declared_dcids
        assert is_declared == (expected.locality == "local"), (
            f"{label}: spec is mislabeled; '{expected.dcid}' is "
            f"{'' if is_declared else 'not '}declared in the dataset MCFs."
        )

        node = targets.get(expected.dcid)
        assert node is not None, (
            f"'{spec.node_dcid} {spec.expression}' did not return target '{expected.dcid}'. "
            f"Got: {sorted(targets)}"
        )
        types = list(node.types or [])
        assert node.name, (
            f"{label} has an empty name. For a remote target this means Mixer did not "
            "hydrate it from Base DC (e.g. a local Node row is shadowing it); for a local "
            "target it means the Spanner node is missing its name."
        )
        assert types, f"{label} has no types."
        assert types != [_UNRESOLVED_TYPE], (
            f"{label} has types {types}. Remote targets must be hydrated from Base DC "
            "and local targets must resolve from Spanner."
        )
        if expected.name is not None:
            assert node.name == expected.name, (
                f"{label} name is '{node.name}', expected '{expected.name}'"
            )
        missing_types = set(expected.types) - set(types)
        assert not missing_types, f"{label} missing types {missing_types}; got {types}"
