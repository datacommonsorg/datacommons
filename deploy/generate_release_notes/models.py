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

"""Data models for Data Commons Platform (DCP) release notes generation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SOPCategory(str, Enum):
    """Standard SOP Categories for Data Commons Platform Release Notes."""

    SPANNER_APIS = "Spanner Graph & APIs"
    INGESTION_SAFETY = "Ingestion & Safety"
    SEARCH_WEBSITE = "Search & Website"
    INFRA_TOOLING = "Infra & Tooling"


@dataclass
class PullRequest:
    """Represents a single merged GitHub Pull Request."""

    number: int
    title: str
    body: str
    author: str
    url: str
    merged_at: str
    repo_name: str
    labels: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    commit_shas: List[str] = field(default_factory=list)
    target_components: List[str] = field(default_factory=list)

    @property
    def qualified_id(self) -> str:
        """Returns a qualified repo#number identifier (e.g. 'datacommons#188' or 'import#42')."""
        repo_short = self.repo_name.split("/")[-1]
        return f"{repo_short}#{self.number}"


@dataclass
class ComponentVersionInfo:
    """Version, SHA, and timestamp details for a single component/image."""

    component_id: str
    component_name: str
    repo_name: str
    previous_version: str
    new_version: str
    previous_sha: Optional[str] = None
    new_sha: Optional[str] = None
    prev_timestamp: Optional[str] = None
    new_timestamp: Optional[str] = None
    image_uri: Optional[str] = None


@dataclass
class FeatureUpdate:
    """Represents a synthesized feature update combining one or more PRs."""

    id: str
    title: str
    description: str
    category: str  # Must match one of SOPCategory values
    target_components: List[str] = field(default_factory=list)
    included_prs: List[str] = field(default_factory=list)  # Qualified PR IDs e.g. ["datacommons#188"]
    pr_contributions: Dict[str, str] = field(default_factory=dict)  # Maps PR ID -> Specific contribution summary
    is_dcp_relevant: bool = True
    breaking_changes: Optional[str] = None


@dataclass
class ReleaseInfoManifest:
    """Container for all raw sourced information and mapped PRs for a release."""

    previous_version: str
    new_version: str
    components: Dict[str, ComponentVersionInfo] = field(default_factory=dict)
    pull_requests_by_component: Dict[str, List[PullRequest]] = field(
        default_factory=dict
    )
    all_pull_requests: List[PullRequest] = field(default_factory=list)
    additional_instructions: Optional[str] = None
