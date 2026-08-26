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

from tests.integration.core.config_schema import SpecializationEdgeSpec
from tests.integration.core.spanner_client import SpannerClient
from tests.integration.core.target import DCPTarget


class TestSVGHierarchy:
    """Validates Statistical Variable Group (SVG) parent-child hierarchy generation."""

    def test_svg_hierarchy_specialization(
        self,
        seeded_testbed,
        dcp_target: DCPTarget,
        spanner_client: SpannerClient,
        specialization_edge_spec: SpecializationEdgeSpec | None,
    ):
        """Verifies that SVG specialization edge exists in Spanner Edge table."""
        if dcp_target.instance_name in ("local", "emulated"):
            pytest.skip(
                "Postprocessing BigQuery aggregation is skipped in local emulated mode."
            )

        if not specialization_edge_spec:
            pytest.skip(
                "No SVG specialization edges defined in manifest or postprocessing stage disabled."
            )

        sql = (
            "SELECT subject_id, predicate, object_id FROM Edge "
            "WHERE subject_id = @sid AND predicate = 'specializationOf' AND object_id = @parent LIMIT 1"
        )
        params = {
            "sid": specialization_edge_spec.subject_id,
            "parent": specialization_edge_spec.parent_svg,
        }
        rows = spanner_client.query(sql, params=params)
        assert len(rows) > 0, (
            f"Expected SVG specialization edge ({specialization_edge_spec.subject_id} -> specializationOf -> {specialization_edge_spec.parent_svg}) "
            "not found in Spanner Edge table"
        )
