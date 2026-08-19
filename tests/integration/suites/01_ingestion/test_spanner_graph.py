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

from tests.integration.core.config_schema import ExpectedEdge, ExpectedNode
from tests.integration.core.spanner_client import SpannerClient


class TestSpannerGraphNodesAndEdges:
    """Validates declared knowledge graph nodes and triples in Cloud Spanner Node and Edge tables."""

    def test_spanner_node_exists(
        self,
        seeded_testbed,
        spanner_client: SpannerClient,
        expected_node_spec: ExpectedNode | None,
    ):
        """Verifies specific node exists in Spanner Node table with expected types."""
        if not expected_node_spec:
            pytest.skip("No nodes defined in manifest or ingestion stage disabled.")

        node = spanner_client.get_node(expected_node_spec.subject_id)
        assert node is not None, (
            f"Expected node '{expected_node_spec.subject_id}' not found in Spanner Node table"
        )

        if expected_node_spec.expected_types:
            node_types = node.get("types", []) or []
            for t in expected_node_spec.expected_types:
                assert t in node_types or any(t in str(x) for x in node_types), (
                    f"Node '{expected_node_spec.subject_id}' missing expected type '{t}'. Actual types: {node_types}"
                )

    def test_spanner_edge_exists(
        self,
        seeded_testbed,
        spanner_client: SpannerClient,
        expected_edge_spec: ExpectedEdge | None,
    ):
        """Verifies specific (subject, predicate, object) edge exists in Spanner Edge table."""
        if not expected_edge_spec:
            pytest.skip("No edges defined in manifest or ingestion stage disabled.")

        sql = (
            "SELECT subject_id, predicate, object_id FROM Edge "
            "WHERE subject_id = @sid AND predicate = @pred AND object_id = @obj LIMIT 1"
        )
        params = {
            "sid": expected_edge_spec.subject_id,
            "pred": expected_edge_spec.predicate,
            "obj": expected_edge_spec.object_id,
        }
        rows = spanner_client.query(sql, params=params)
        assert len(rows) > 0, (
            f"Expected edge ({expected_edge_spec.subject_id} -> {expected_edge_spec.predicate} -> {expected_edge_spec.object_id}) "
            "not found in Spanner Edge table"
        )
