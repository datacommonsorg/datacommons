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

"""Unit tests for config_schema.py (manifest parsing, loading, and merging)."""

import pytest

from tests.integration.core.config_schema import (
    ExpectedEdge,
    ExpectedNode,
    IndicatorResolutionSpec,
    IngestionManifestConfig,
    MCPAgentManifestConfig,
    MCPToolCallSpec,
    NodeQuerySpec,
    PointObservationSpec,
    PostprocessingManifestConfig,
    SDMXDataQuerySpec,
    SDMXManifestConfig,
    ServingAPIManifestConfig,
    SpannerExpectations,
    StageGating,
    TestManifest,
    _parse_dataclass,
    load_test_manifest,
    merge_manifests,
)


def test_load_single_manifest_by_name():
    """Verifies that passing a dataset name (e.g. 'foobar_wages') resolves and loads its test_spec.yaml."""
    manifest = load_test_manifest("foobar_wages")
    assert manifest.name == "foobar_wages"
    assert manifest.stages.ingestion is True
    assert manifest.stages.serving_api is True
    assert manifest.ingestion.spanner_expectations.exact_observation_count == 1242
    assert len(manifest.ingestion.spanner_expectations.expected_nodes) > 0


def test_load_single_manifest_by_relative_path():
    """Verifies loading a manifest via a relative path."""
    manifest = load_test_manifest(
        "tests/integration/test_data/foobar_education/test_spec.yaml"
    )
    assert manifest.name == "foobar_education"
    assert manifest.stages.sdmx is False
    assert manifest.ingestion.spanner_expectations.exact_observation_count == 6


def test_missing_manifest_raises_file_not_found():
    """Verifies that attempting to load a non-existent dataset raises FileNotFoundError."""
    with pytest.raises(
        FileNotFoundError, match="Test manifest or dataset spec not found"
    ):
        load_test_manifest("non_existent_dataset_12345")


def test_parse_dataclass_gracefully_ignores_unknown_fields():
    """Verifies that unknown or legacy fields in raw YAML dictionaries are safely ignored."""
    raw_dict = {
        "name": "sample_dataset",
        "description": "A sample dataset",
        "unknown_legacy_field": "some_value",
        "schema_version": "99.9",
        "stages": {"ingestion": True, "future_stage": False},
    }
    manifest = _parse_dataclass(TestManifest, raw_dict)
    assert manifest.name == "sample_dataset"
    assert manifest.description == "A sample dataset"
    assert manifest.stages.ingestion is True


def test_merge_manifests_basic():
    """Verifies metadata merging and stage union logic."""
    m1 = TestManifest(
        name="dataset_a",
        description="Dataset A",
        stages=StageGating(ingestion=True, sdmx=False),
    )
    m2 = TestManifest(
        name="dataset_b",
        description="Dataset B",
        stages=StageGating(ingestion=True, sdmx=True),
    )

    merged = merge_manifests([m1, m2])
    assert merged.name == "dataset_a+dataset_b"
    assert merged.stages.ingestion is True
    assert merged.stages.sdmx is True  # sdmx is True if any manifest enables it


def test_merge_manifests_observation_count_summation():
    """Verifies exact observation counts sum across all active manifests."""
    m1 = TestManifest(
        name="m1",
        ingestion=IngestionManifestConfig(
            dataset_dirs=["dir1"],
            spanner_expectations=SpannerExpectations(exact_observation_count=100),
        ),
    )
    m2 = TestManifest(
        name="m2",
        ingestion=IngestionManifestConfig(
            dataset_dirs=["dir2"],
            spanner_expectations=SpannerExpectations(exact_observation_count=50),
        ),
    )

    merged = merge_manifests([m1, m2])
    assert merged.ingestion.spanner_expectations.exact_observation_count == 150
    assert merged.ingestion.dataset_dirs == ["dir1", "dir2"]


def test_merge_manifests_node_and_edge_deduplication():
    """Verifies that duplicate nodes and edges across manifests are deduplicated."""
    node_dup = ExpectedNode(subject_id="country/USA", expected_types=["Place"])
    node_unique = ExpectedNode(subject_id="country/FRA", expected_types=["Place"])

    edge_dup = ExpectedEdge(subject_id="A", predicate="memberOf", object_id="B")
    edge_unique = ExpectedEdge(subject_id="C", predicate="memberOf", object_id="D")

    m1 = TestManifest(
        name="m1",
        ingestion=IngestionManifestConfig(
            spanner_expectations=SpannerExpectations(
                expected_nodes=[node_dup],
                expected_edges=[edge_dup],
            )
        ),
    )
    m2 = TestManifest(
        name="m2",
        ingestion=IngestionManifestConfig(
            spanner_expectations=SpannerExpectations(
                expected_nodes=[node_dup, node_unique],
                expected_edges=[edge_dup, edge_unique],
            )
        ),
    )

    merged = merge_manifests([m1, m2])
    assert len(merged.ingestion.spanner_expectations.expected_nodes) == 2
    assert {
        n.subject_id for n in merged.ingestion.spanner_expectations.expected_nodes
    } == {"country/USA", "country/FRA"}

    assert len(merged.ingestion.spanner_expectations.expected_edges) == 2
    assert {
        (e.subject_id, e.predicate, e.object_id)
        for e in merged.ingestion.spanner_expectations.expected_edges
    } == {
        ("A", "memberOf", "B"),
        ("C", "memberOf", "D"),
    }


def test_merge_manifests_accumulates_specs():
    """Verifies that queries across all layers (Embeddings, SDK, SDMX, MCP) accumulate properly."""
    m1 = TestManifest(
        name="m1",
        postprocessing=PostprocessingManifestConfig(
            indicator_resolutions=[IndicatorResolutionSpec(query="wages")],
        ),
        serving_api=ServingAPIManifestConfig(
            nodes=[NodeQuerySpec(node_dcid="average_annual_wage")],
            point_observations=[
                PointObservationSpec(
                    observation_about=["country/USA"], variables=["average_annual_wage"]
                )
            ],
            sdmx_3_0=SDMXManifestConfig(
                data_queries=[SDMXDataQuerySpec(expected_csv_contains=["wage"])]
            ),
        ),
        mcp_agent=MCPAgentManifestConfig(
            tool_calls=[MCPToolCallSpec(tool_name="search_indicators")]
        ),
    )
    m2 = TestManifest(
        name="m2",
        postprocessing=PostprocessingManifestConfig(
            indicator_resolutions=[IndicatorResolutionSpec(query="literacy")],
        ),
        serving_api=ServingAPIManifestConfig(
            nodes=[NodeQuerySpec(node_dcid="foobar/YouthLiteracyRate")],
            point_observations=[
                PointObservationSpec(
                    observation_about=["country/USA"],
                    variables=["foobar/YouthLiteracyRate"],
                )
            ],
        ),
        mcp_agent=MCPAgentManifestConfig(
            tool_calls=[MCPToolCallSpec(tool_name="get_observations")]
        ),
    )

    merged = merge_manifests([m1, m2])
    assert len(merged.postprocessing.indicator_resolutions) == 2
    assert len(merged.serving_api.nodes) == 2
    assert len(merged.serving_api.point_observations) == 2
    assert len(merged.serving_api.sdmx_3_0.data_queries) == 1
    assert len(merged.mcp_agent.tool_calls) == 2


def test_load_test_manifest_multi_sources():
    """Verifies loading multiple manifests via a list or comma-separated string."""
    # Multi-item list
    merged_list = load_test_manifest(["foobar_wages", "foobar_education"])
    assert merged_list.name == "foobar_wages+foobar_education"
    assert merged_list.ingestion.spanner_expectations.exact_observation_count == 1248

    # Comma-separated string
    merged_str = load_test_manifest("foobar_wages,foobar_education")
    assert merged_str.name == "foobar_wages+foobar_education"
    assert merged_str.ingestion.spanner_expectations.exact_observation_count == 1248


def test_load_health_aid_manifest():
    """Verifies loading the health_aid multi-entity dataset manifest."""
    manifest = load_test_manifest("health_aid")
    assert manifest.name == "health_aid"
    assert manifest.stages.ingestion is True
    assert manifest.stages.serving_api is True
    assert manifest.stages.sdmx is True
    assert manifest.ingestion.spanner_expectations.exact_observation_count == 16

    # Verify multi-entity nodes and edges in schema
    node_ids = {
        n.subject_id for n in manifest.ingestion.spanner_expectations.expected_nodes
    }
    assert "GlobalHealthAidGroup" in node_ids
    assert "GlobalHealthAidSource" in node_ids
    assert "GlobalHealthAidProvenance" in node_ids
    assert "donorPlace" in node_ids
    assert "recipientPlace" in node_ids
    assert "HealthAidFunding" in node_ids

    # Verify multi-entity node fetch spec (->observationProperties)
    assert len(manifest.serving_api.nodes) == 1
    assert manifest.serving_api.nodes[0].node_dcid == "HealthAidFunding"
    assert manifest.serving_api.nodes[0].expression == "->observationProperties"
    assert manifest.serving_api.nodes[0].expected_values == [
        "donorPlace",
        "recipientPlace",
        "medicalCondition",
    ]

    # Verify SDMX data query specs (commented out pending Mixer GQL fix)
    data_queries = manifest.serving_api.sdmx_3_0.data_queries
    assert len(data_queries) == 0

    # Verify SDMX availability query specs (commented out pending Mixer GQL fix)
    avail_queries = manifest.serving_api.sdmx_3_0.availability_queries
    assert len(avail_queries) == 0

    # Verify MCP tool call spec (commented out pending Mixer GQL fix)
    tool_calls = manifest.mcp_agent.tool_calls
    assert len(tool_calls) == 0
