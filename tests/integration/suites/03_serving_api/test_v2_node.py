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

from tests.integration.core.config_schema import NodeQuerySpec


class TestV2Node:
    """Validates Node properties and graph edge inspection via datacommons-client."""

    def test_node_fetch_expression(
        self, seeded_testbed, dc_client, node_query_spec: NodeQuerySpec | None
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
