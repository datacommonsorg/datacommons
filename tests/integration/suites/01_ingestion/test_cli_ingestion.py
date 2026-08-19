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

from tests.integration.core.cli_runner import DatacommonsCLI
from tests.integration.core.config_schema import TestManifest
from tests.integration.core.spanner_client import SpannerClient


class TestCLIIngestion:
    """Validates CLI workspace inspection and seeded Cloud Spanner observations."""

    def test_01_cli_ingest_show_config(self, dcp_cli: DatacommonsCLI):
        """Validates that 'datacommons admin ingest show-config' runs and outputs valid configuration."""
        res = dcp_cli.run(["admin", "ingest", "show-config"])
        assert res.exit_code == 0, f"CLI ingest show-config failed: {res.output}"
        assert len(res.output) > 0

    def test_02_spanner_seeded_observations(
        self, seeded_testbed, spanner_client: SpannerClient, test_manifest: TestManifest
    ):
        """Verifies Spanner observation count against manifest expectation."""
        if not test_manifest.stages.ingestion:
            pytest.skip("Ingestion stage disabled in test manifest.")

        count = spanner_client.count_observations()
        exp = test_manifest.ingestion.spanner_expectations

        if exp.exact_observation_count is not None:
            assert count == exp.exact_observation_count, (
                f"Expected exact {exp.exact_observation_count} observations in Spanner, found {count}"
            )
        elif exp.min_observation_count is not None:
            assert count >= exp.min_observation_count, (
                f"Expected at least {exp.min_observation_count} observations in Spanner, found {count}"
            )
        else:
            assert count > 0, (
                f"Expected non-zero observations in Spanner, found {count}"
            )
