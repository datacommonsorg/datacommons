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

"""Typed schema definitions, loader, and multi-manifest merger for declarative test manifests."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class StageGating:
    ingestion: bool = True
    postprocessing: bool = True
    serving_api: bool = True
    mcp_agent: bool = True
    sdmx: bool = True


@dataclass
class ExpectedNode:
    subject_id: str
    expected_types: list[str] = field(default_factory=list)


@dataclass
class ExpectedEdge:
    subject_id: str
    predicate: str
    object_id: str


@dataclass
class SpannerExpectations:
    exact_observation_count: int | None = None
    min_observation_count: int | None = None
    expected_nodes: list[ExpectedNode] = field(default_factory=list)
    expected_edges: list[ExpectedEdge] = field(default_factory=list)


@dataclass
class IngestionManifestConfig:
    dataset_dirs: list[str] = field(default_factory=list)
    spanner_expectations: SpannerExpectations = field(
        default_factory=SpannerExpectations
    )


@dataclass
class IndicatorResolutionSpec:
    query: str
    target: str = "custom_only"
    expected_candidate_dcids: list[str] = field(default_factory=list)


@dataclass
class SpecializationEdgeSpec:
    subject_id: str
    parent_svg: str = "dc/g/Root"


@dataclass
class SVGHierarchySpec:
    expected_specialization_edges: list[SpecializationEdgeSpec] = field(
        default_factory=list
    )


@dataclass
class PostprocessingManifestConfig:
    svg_hierarchy: SVGHierarchySpec = field(default_factory=SVGHierarchySpec)
    indicator_resolutions: list[IndicatorResolutionSpec] = field(default_factory=list)


@dataclass
class NodeQuerySpec:
    node_dcid: str
    expression: str = "->name"
    expected_values: list[str] = field(default_factory=list)


@dataclass
class PointObservationSpec:
    observation_about: list[str] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)
    date: str = "LATEST"
    expected_places_with_data: list[str] = field(default_factory=list)


@dataclass
class SeriesObservationSpec:
    observation_about: list[str] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)
    min_series_length: int = 1


@dataclass
class SDMXDataQuerySpec:
    dataflow: str = "DC/DF_OBS/1.0.0/*"
    constraints: dict[str, str] = field(default_factory=dict)
    format: str = "csv"
    expected_status: int = 200
    expected_csv_contains: list[str] = field(default_factory=list)
    expected_error_contains: str | None = None


@dataclass
class SDMXAvailabilityQuerySpec:
    dataflow: str = "DC/DF_OBS/1.0.0/*/provenance"
    constraints: dict[str, str] = field(default_factory=dict)
    expected_status: int = 200
    expected_provenance: str | None = None
    expected_values_contain: list[str] = field(default_factory=list)
    expected_error_contains: str | None = None


@dataclass
class SDMXManifestConfig:
    data_queries: list[SDMXDataQuerySpec] = field(default_factory=list)
    availability_queries: list[SDMXAvailabilityQuerySpec] = field(default_factory=list)


@dataclass
class ServingAPIManifestConfig:
    nodes: list[NodeQuerySpec] = field(default_factory=list)
    point_observations: list[PointObservationSpec] = field(default_factory=list)
    series_observations: list[SeriesObservationSpec] = field(default_factory=list)
    sdmx_3_0: SDMXManifestConfig = field(default_factory=SDMXManifestConfig)


@dataclass
class MCPToolCallSpec:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    expected_match_dcids: list[str] = field(default_factory=list)


@dataclass
class MCPAgentManifestConfig:
    tool_calls: list[MCPToolCallSpec] = field(default_factory=list)


@dataclass
class TestManifest:
    __test__ = False
    name: str = "custom_test_manifest"
    description: str = ""
    stages: StageGating = field(default_factory=StageGating)
    includes: list[str] = field(default_factory=list)
    ingestion: IngestionManifestConfig = field(default_factory=IngestionManifestConfig)
    postprocessing: PostprocessingManifestConfig = field(
        default_factory=PostprocessingManifestConfig
    )
    serving_api: ServingAPIManifestConfig = field(
        default_factory=ServingAPIManifestConfig
    )
    mcp_agent: MCPAgentManifestConfig = field(default_factory=MCPAgentManifestConfig)


def _parse_dataclass(cls, data: Any) -> Any:
    """Recursively converts dictionaries to strongly typed dataclass instances."""
    if data is None:
        return cls()
    if not isinstance(data, dict):
        return data

    kwargs = {}
    for field_name, field_def in getattr(cls, "__dataclass_fields__", {}).items():
        if field_name not in data:
            continue
        val = data[field_name]

        field_type = field_def.type
        if hasattr(field_type, "__origin__") and field_type.__origin__ is list:
            elem_type = field_type.__args__[0]
            if hasattr(elem_type, "__dataclass_fields__"):
                kwargs[field_name] = [_parse_dataclass(elem_type, item) for item in val]
            else:
                kwargs[field_name] = val
        elif hasattr(field_type, "__dataclass_fields__"):
            kwargs[field_name] = _parse_dataclass(field_type, val)
        else:
            kwargs[field_name] = val

    return cls(**kwargs)


def merge_manifests(manifests: Sequence[TestManifest]) -> TestManifest:
    """Combines multiple dataset-level manifests into a single composite TestManifest."""
    if not manifests:
        return TestManifest()
    if len(manifests) == 1:
        return manifests[0]

    merged_name = "+".join(m.name for m in manifests)
    merged_desc = "; ".join(m.description for m in manifests if m.description)

    # 1. Stages: enabled if enabled in ANY manifest
    stages = StageGating(
        ingestion=any(m.stages.ingestion for m in manifests),
        postprocessing=any(m.stages.postprocessing for m in manifests),
        serving_api=any(m.stages.serving_api for m in manifests),
        mcp_agent=any(m.stages.mcp_agent for m in manifests),
        sdmx=any(m.stages.sdmx for m in manifests),
    )

    # 2. Ingestion
    dataset_dirs: list[str] = []
    for m in manifests:
        for d in m.ingestion.dataset_dirs:
            if d not in dataset_dirs:
                dataset_dirs.append(d)

    # Exact count sums if all have exact counts, else None
    exact_counts = [
        m.ingestion.spanner_expectations.exact_observation_count for m in manifests
    ]
    total_exact = (
        sum(c for c in exact_counts if c is not None)
        if all(c is not None for c in exact_counts)
        else None
    )

    # Min count sums
    min_counts = [
        m.ingestion.spanner_expectations.min_observation_count
        for m in manifests
        if m.ingestion.spanner_expectations.min_observation_count is not None
    ]
    total_min = sum(min_counts) if min_counts else None

    # Deduplicate nodes by subject_id
    seen_nodes = set()
    expected_nodes: list[ExpectedNode] = []
    for m in manifests:
        for n in m.ingestion.spanner_expectations.expected_nodes:
            if n.subject_id not in seen_nodes:
                seen_nodes.add(n.subject_id)
                expected_nodes.append(n)

    # Deduplicate edges by (subject_id, predicate, object_id)
    seen_edges = set()
    expected_edges: list[ExpectedEdge] = []
    for m in manifests:
        for e in m.ingestion.spanner_expectations.expected_edges:
            edge_key = (e.subject_id, e.predicate, e.object_id)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                expected_edges.append(e)

    spanner_exp = SpannerExpectations(
        exact_observation_count=total_exact,
        min_observation_count=total_min,
        expected_nodes=expected_nodes,
        expected_edges=expected_edges,
    )
    ingestion = IngestionManifestConfig(
        dataset_dirs=dataset_dirs, spanner_expectations=spanner_exp
    )

    # 3. Postprocessing
    seen_spec_edges = set()
    spec_edges: list[SpecializationEdgeSpec] = []
    resolutions: list[IndicatorResolutionSpec] = []
    for m in manifests:
        for se in m.postprocessing.svg_hierarchy.expected_specialization_edges:
            k = (se.subject_id, se.parent_svg)
            if k not in seen_spec_edges:
                seen_spec_edges.add(k)
                spec_edges.append(se)
        resolutions.extend(m.postprocessing.indicator_resolutions)

    postprocessing = PostprocessingManifestConfig(
        svg_hierarchy=SVGHierarchySpec(expected_specialization_edges=spec_edges),
        indicator_resolutions=resolutions,
    )

    # 4. Serving API
    nodes: list[NodeQuerySpec] = []
    point_obs: list[PointObservationSpec] = []
    series_obs: list[SeriesObservationSpec] = []
    sdmx_data: list[SDMXDataQuerySpec] = []
    sdmx_avail: list[SDMXAvailabilityQuerySpec] = []

    for m in manifests:
        nodes.extend(m.serving_api.nodes)
        point_obs.extend(m.serving_api.point_observations)
        series_obs.extend(m.serving_api.series_observations)
        sdmx_data.extend(m.serving_api.sdmx_3_0.data_queries)
        sdmx_avail.extend(m.serving_api.sdmx_3_0.availability_queries)

    serving_api = ServingAPIManifestConfig(
        nodes=nodes,
        point_observations=point_obs,
        series_observations=series_obs,
        sdmx_3_0=SDMXManifestConfig(
            data_queries=sdmx_data, availability_queries=sdmx_avail
        ),
    )

    # 5. MCP Agent
    tool_calls: list[MCPToolCallSpec] = []
    for m in manifests:
        tool_calls.extend(m.mcp_agent.tool_calls)

    mcp_agent = MCPAgentManifestConfig(tool_calls=tool_calls)

    return TestManifest(
        name=merged_name,
        description=merged_desc,
        stages=stages,
        ingestion=ingestion,
        postprocessing=postprocessing,
        serving_api=serving_api,
        mcp_agent=mcp_agent,
    )


def _load_single_manifest(manifest_path_or_str: str | Path) -> TestManifest:
    """Loads a single YAML test manifest or dataset folder."""
    repo_root = Path(__file__).resolve().parents[3]
    test_data_root = repo_root / "tests" / "integration" / "test_data"

    # Search candidates in order:
    # 1. Exact path
    # 2. Relative to repo root
    # 3. Inside tests/integration/test_data/<name>
    candidates = [
        Path(manifest_path_or_str),
        repo_root / manifest_path_or_str,
        test_data_root / manifest_path_or_str,
        test_data_root / manifest_path_or_str / "test_spec.yaml",
    ]

    target_file = None
    for cand in candidates:
        cand_resolved = cand.resolve()
        if cand_resolved.is_file():
            target_file = cand_resolved
            break
        if cand_resolved.is_dir() and (cand_resolved / "test_spec.yaml").is_file():
            target_file = (cand_resolved / "test_spec.yaml").resolve()
            break

    if not target_file:
        raise FileNotFoundError(
            f"Test manifest or dataset spec not found: '{manifest_path_or_str}'"
        )

    with open(target_file, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    manifest = _parse_dataclass(TestManifest, data)

    # If this manifest has 'includes', recursively load and merge them
    if manifest.includes:
        included_manifests = [load_test_manifest(inc) for inc in manifest.includes]
        included_manifests.append(manifest)
        return merge_manifests(included_manifests)

    return manifest


def load_test_manifest(
    manifest_input: str | Path | Sequence[str | Path],
) -> TestManifest:
    """Loads and parses one or more YAML test manifests, merging them if multiple are provided."""
    # Handle list or tuple
    if isinstance(manifest_input, (list, tuple)):
        # Flatten any comma-separated entries
        flat_paths: list[str] = []
        for item in manifest_input:
            if isinstance(item, str) and "," in item:
                flat_paths.extend([p.strip() for p in item.split(",") if p.strip()])
            else:
                flat_paths.append(str(item))
        loaded = [_load_single_manifest(p) for p in flat_paths]
        return merge_manifests(loaded)

    # Handle comma-separated string
    if isinstance(manifest_input, str) and "," in manifest_input:
        paths = [p.strip() for p in manifest_input.split(",") if p.strip()]
        loaded = [_load_single_manifest(p) for p in paths]
        return merge_manifests(loaded)

    return _load_single_manifest(manifest_input)
