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

from tests.integration.core.config_schema import IndicatorResolutionSpec


class TestEmbeddings:
    """Validates vector embeddings & semantic search resolution via official datacommons-client."""

    def test_indicator_resolution(
        self, seeded_testbed, dc_client, indicator_spec: IndicatorResolutionSpec | None
    ):
        """Verifies semantic resolution for a declared indicator query."""
        if not indicator_spec:
            pytest.skip(
                "No indicator queries defined in manifest or postprocessing stage disabled."
            )

        if seeded_testbed.instance_name in ("local", "emulated"):
            pytest.skip(
                "Vector embeddings resolution disabled in local emulated mode."
            )

        try:
            res = dc_client.resolve.fetch_indicators(queries=[indicator_spec.query])
            assert res is not None

            candidates = []
            if hasattr(res, "entities") and res.entities:
                for ent in res.entities:
                    if hasattr(ent, "candidates"):
                        candidates.extend(
                            [c.dcid for c in ent.candidates if hasattr(c, "dcid")]
                        )
            elif isinstance(res, dict) and "entities" in res:
                for ent in res["entities"]:
                    candidates.extend(
                        c.get("dcid")
                        for c in ent.get("candidates", [])
                        if c.get("dcid")
                    )

            assert len(candidates) > 0, (
                f"No indicator candidates returned for query '{indicator_spec.query}'"
            )

            if indicator_spec.expected_candidate_dcids:
                matched = any(
                    dcid in candidates
                    for dcid in indicator_spec.expected_candidate_dcids
                )
                assert matched, (
                    f"Query '{indicator_spec.query}' resolved to {candidates[:5]}, "
                    f"expected at least one of {indicator_spec.expected_candidate_dcids}"
                )
        except Exception as e:
            pytest.fail(
                f"Indicator resolution failed for '{indicator_spec.query}': {e}"
            )
