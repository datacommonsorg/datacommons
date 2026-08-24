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

from tests.integration.core.config_schema import (
    PointObservationSpec,
    SeriesObservationSpec,
)


class TestV2Observation:
    """Validates point and series observation queries via official datacommons-client."""

    def test_observation_point_query(
        self, seeded_testbed, dc_client, point_obs_spec: PointObservationSpec | None
    ):
        """Verifies point observations by entity and variable DCIDs."""
        if not point_obs_spec:
            pytest.skip(
                "No point observation queries defined in manifest or serving_api stage disabled."
            )

        res = dc_client.observation.fetch_observations_by_entity_dcid(
            date=point_obs_spec.date,
            entity_dcids=point_obs_spec.observation_about,
            variable_dcids=point_obs_spec.variables,
        )
        assert res is not None, (
            f"Expected non-null response for point query: {point_obs_spec}"
        )

        text_repr = str(res)
        for place in point_obs_spec.expected_places_with_data:
            assert place in text_repr, (
                f"Expected place '{place}' with observations in response: {text_repr[:300]}"
            )

    def test_observation_series_query(
        self, seeded_testbed, dc_client, series_obs_spec: SeriesObservationSpec | None
    ):
        """Verifies full time-series observation data by entity and variable DCIDs."""
        if not series_obs_spec:
            pytest.skip(
                "No series observation queries defined in manifest or serving_api stage disabled."
            )

        res = dc_client.observation.fetch_observations_by_entity_dcid(
            date="",
            entity_dcids=series_obs_spec.observation_about,
            variable_dcids=series_obs_spec.variables,
        )
        assert res is not None, (
            f"Expected non-null response for series query: {series_obs_spec}"
        )
        assert len(str(res)) > 50, f"Series observation response too short: {res}"
