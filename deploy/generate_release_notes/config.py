# Copyright 2026 Google LLC
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

"""Configuration and multi-repository component mappings for DCP release notes generation."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

DEFAULT_GITHUB_ORG = "datacommonsorg"


@dataclass
class SourceRule:
    """Source repository rule with optional file path filter."""

    repo: str
    path_filter: Optional[str] = (
        None  # If set, only PRs modifying this path match this component
    )


@dataclass
class ComponentConfig:
    """Configuration for a tracked repository/component in DCP releases."""

    id: str  # Unique key (e.g. 'dcp', 'preprocessing', 'services')
    name: str  # Human-readable name for release notes
    artifact_type: (
        str  # 'dcp_platform', 'docker_services', 'docker_data', etc.
    )
    image_uri: Optional[str] = None  # Primary container image URI
    default_tag_prefix: str = "v"  # Tag prefix (e.g. 'v' for 'v1.1.2')
    sources: List[SourceRule] = field(
        default_factory=list
    )  # Multi-repo contributing sources


# Master registry of all tracked components across Data Commons repositories
COMPONENTS: Dict[str, ComponentConfig] = {
    "dcp": ComponentConfig(
        id="dcp",
        name="DCP Monorepo & Infra (CLI, Admin, DB, Terraform)",
        artifact_type="dcp_platform",
        image_uri=None,
        default_tag_prefix="v",
        sources=[
            SourceRule(repo="datacommonsorg/datacommons"),
        ],
    ),
    "services": ComponentConfig(
        id="services",
        name="Core Services (Website, Mixer, MCP)",
        artifact_type="docker_services",
        image_uri="gcr.io/datcom-ci/datacommons-services",
        default_tag_prefix="v",
        sources=[
            SourceRule(repo="datacommonsorg/website"),  # All non-cdc_data website PRs
            SourceRule(repo="datacommonsorg/mixer"),  # All mixer PRs
            SourceRule(repo="datacommonsorg/agent-toolkit"),  # All MCP PRs
        ],
    ),
    "preprocessing": ComponentConfig(
        id="preprocessing",
        name="Data Preprocessor (datacommons-data)",
        artifact_type="docker_data",
        image_uri="gcr.io/datcom-ci/datacommons-data",
        default_tag_prefix="v",
        sources=[
            SourceRule(repo="datacommonsorg/import", path_filter="simple/"),
            SourceRule(
                repo="datacommonsorg/website", path_filter="build/cdc_data/"
            ),
        ],
    ),
    "dataflow_worker": ComponentConfig(
        id="dataflow_worker",
        name="Dataflow Ingestion Worker",
        artifact_type="dataflow_template",
        image_uri="us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion",
        default_tag_prefix="v",
        sources=[
            SourceRule(
                repo="datacommonsorg/import", path_filter="pipeline/ingestion/"
            ),
        ],
    ),
    "ingestion_helper": ComponentConfig(
        id="ingestion_helper",
        name="Ingestion Helper Service",
        artifact_type="docker_helper",
        image_uri="gcr.io/datcom-ci/datacommons-ingestion-helper",
        default_tag_prefix="v",
        sources=[
            SourceRule(
                repo="datacommonsorg/import",
                path_filter="pipeline/workflow/ingestion-helper/",
            ),
        ],
    ),
    "postprocessing": ComponentConfig(
        id="postprocessing",
        name="Postprocessing Aggregation Helper Service",
        artifact_type="docker_helper",
        image_uri="gcr.io/datcom-ci/datacommons-aggregation-helper",
        default_tag_prefix="v",
        sources=[
            SourceRule(
                repo="datacommonsorg/import",
                path_filter="pipeline/workflow/aggregation-helper/",
            ),
        ],
    ),
}
