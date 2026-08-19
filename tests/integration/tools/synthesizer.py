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

"""Developer tool that auto-generates test_spec.yaml from raw dataset CSV, MCF, and config.json files."""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

# Ensure repository root is in Python sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


import yaml

from tests.integration.core.config_schema import (
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
    TestManifest,
)


class DatasetSynthesizer:
    """Inspects dataset directories and auto-generates a TestManifest."""

    def __init__(self, dataset_dirs: list[str | Path]):
        self.dataset_dirs = [Path(d).resolve() for d in dataset_dirs]

    def synthesize(self, manifest_name: str | None = None) -> TestManifest:
        expected_nodes: list[ExpectedNode] = []
        indicator_resolutions: list[IndicatorResolutionSpec] = []
        point_observations: list[PointObservationSpec] = []
        node_queries: list[NodeQuerySpec] = []
        sdmx_data_queries: list[SDMXDataQuerySpec] = []
        mcp_tool_calls: list[MCPToolCallSpec] = []

        all_stat_vars: set[str] = set()
        all_provenances: set[str] = set()
        all_places: set[str] = set()

        for d_path in self.dataset_dirs:
            if not d_path.exists() or not d_path.is_dir():
                continue

            # 1. Parse config.json
            config_file = d_path / "config.json"
            cfg_data = {}
            if config_file.exists():
                try:
                    with open(config_file, encoding="utf-8") as f:
                        cfg_data = json.load(f)
                    for item in cfg_data.get("inputFiles", []):
                        prov = item.get("provenance", "").replace("dcid:", "")
                        if prov:
                            all_provenances.add(prov)
                except Exception:
                    pass

            # 2. Parse MCF files for Node DCIDs & types
            for mcf_file in d_path.glob("*.mcf"):
                try:
                    with open(mcf_file, encoding="utf-8") as f:
                        content = f.read()

                    for block in content.split("\n\n"):
                        node_match = re.search(r"Node:\s*dcid:([^\s]+)", block)
                        type_match = re.search(r"typeOf:\s*dcid:([^\s]+)", block)
                        name_match = re.search(r'name:\s*"([^"]+)"', block)

                        if node_match:
                            node_id = node_match.group(1)
                            node_type = type_match.group(1) if type_match else "Node"
                            expected_nodes.append(
                                ExpectedNode(
                                    subject_id=node_id, expected_types=[node_type]
                                )
                            )

                            if node_type in ("StatisticalVariable", "StatVar"):
                                all_stat_vars.add(node_id)
                                human_name = (
                                    name_match.group(1)
                                    if name_match
                                    else node_id.replace("_", " ")
                                )
                                indicator_resolutions.append(
                                    IndicatorResolutionSpec(
                                        query=human_name.lower(),
                                        expected_candidate_dcids=[node_id],
                                    )
                                )
                                mcp_tool_calls.append(
                                    MCPToolCallSpec(
                                        tool_name="search_indicators",
                                        arguments={"query": human_name.lower()},
                                        expected_match_dcids=[node_id],
                                    )
                                )
                            elif node_type in ("Provenance", "Source"):
                                all_provenances.add(node_id)
                except Exception:
                    pass

            # 3. Sample CSV files for observationAbout places using columnMappings from config.json
            entity_col = "observationAbout"
            if config_file.exists():
                try:
                    for item in cfg_data.get("inputFiles", []):
                        col_map = item.get("columnMappings", {})
                        if "dcid:observationAbout" in col_map:
                            entity_col = col_map["dcid:observationAbout"]
                            break
                except Exception:
                    pass

            for csv_file in d_path.glob("*.csv"):
                try:
                    with open(csv_file, encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for i, row in enumerate(reader):
                            if i > 10:
                                break
                            entity = row.get(entity_col)
                            if entity:
                                clean_ent = entity.replace("dcid:", "")
                                all_places.add(clean_ent)
                except Exception:
                    pass

        sample_places = list(all_places)[:3] or ["country/USA"]
        for sv in list(all_stat_vars)[:5]:
            point_observations.append(
                PointObservationSpec(
                    observation_about=sample_places,
                    variables=[sv],
                    date="LATEST",
                    expected_places_with_data=sample_places[:1],
                )
            )
            node_queries.append(
                NodeQuerySpec(
                    node_dcid=sv,
                    expression="->name",
                )
            )
            sdmx_data_queries.append(
                SDMXDataQuerySpec(
                    dataflow="DC/DF_OBS/1.0.0/*",
                    constraints={
                        "variableMeasured": sv,
                        "observationAbout": sample_places[0],
                    },
                    expected_csv_contains=[sv],
                )
            )

        name = manifest_name or (
            self.dataset_dirs[0].name if self.dataset_dirs else "custom_dataset"
        )
        rel_dirs = [str(d) for d in self.dataset_dirs]

        return TestManifest(
            name=name,
            description=f"Auto-synthesized test manifest for {len(self.dataset_dirs)} dataset directories",
            ingestion=IngestionManifestConfig(
                dataset_dirs=rel_dirs,
                spanner_expectations=SpannerExpectations(
                    min_observation_count=1,
                    expected_nodes=expected_nodes,
                ),
            ),
            postprocessing=PostprocessingManifestConfig(
                indicator_resolutions=indicator_resolutions[:5],
            ),
            serving_api=ServingAPIManifestConfig(
                nodes=node_queries[:5],
                point_observations=point_observations,
                sdmx_3_0=SDMXManifestConfig(data_queries=sdmx_data_queries[:3]),
            ),
            mcp_agent=MCPAgentManifestConfig(
                tool_calls=mcp_tool_calls[:3],
            ),
        )

    def save_yaml(self, output_file: str | Path):
        manifest = self.synthesize()
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(manifest.__dict__, f, sort_keys=False)
        print(f"✔ Auto-synthesized test spec written to: {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Auto-synthesize test_spec.yaml from raw dataset directory"
    )
    parser.add_argument(
        "dataset_dir",
        type=str,
        help="Path to raw dataset directory containing .csv and .mcf",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for test_spec.yaml (defaults to <dataset_dir>/test_spec.yaml)",
    )

    args = parser.parse_args()
    d_path = Path(args.dataset_dir).resolve()
    if not d_path.exists() or not d_path.is_dir():
        print(f"Error: Dataset directory '{args.dataset_dir}' does not exist.")
        sys.exit(1)

    out_file = (
        Path(args.output).resolve() if args.output else (d_path / "test_spec.yaml")
    )
    synthesizer = DatasetSynthesizer([d_path])
    synthesizer.save_yaml(out_file)


if __name__ == "__main__":
    main()
