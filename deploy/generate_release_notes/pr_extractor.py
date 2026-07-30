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

"""Step 1: PR Extractor for Data Commons Platform (DCP) release notes generation.

Extracts Pull Requests and image mappings across Data Commons repositories using
gcloud container image tags and GitHub CLI (gh pr list).
"""

from datetime import datetime
import json
import logging
import subprocess
from typing import Dict, List, Optional, Set, Tuple

from deploy.generate_release_notes.config import (
    COMPONENTS,
    ComponentConfig,
    SourceRule,
)
from deploy.generate_release_notes.models import (
    ComponentVersionInfo,
    PullRequest,
    ReleaseInfoManifest,
)

logger = logging.getLogger(__name__)


def normalize_version(version: str) -> str:
    """Strip leading 'v' if present to normalize version string (e.g. 'v1.1.2' -> '1.1.2')."""
    return version[1:] if version.startswith("v") else version


def format_version_tag(version: str) -> str:
    """Ensure leading 'v' is present for Git tags (e.g. '1.1.2' -> 'v1.1.2')."""
    return version if version.startswith("v") else f"v{version}"


class PRExtractor:
    """Extracts all PRs and image mappings between two release versions using gcloud and gh pr list."""

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache

    def resolve_image_tag_info(
        self, image_uri: str, version: str
    ) -> Optional[Dict]:
        """Resolves container image tag in Artifact Registry/GCR via gcloud container images list-tags.

        Returns dict with 'digest', 'tags', and 'timestamp' if found, else None.
        """
        raw_version = normalize_version(version)
        cmd = [
            "gcloud",
            "container",
            "images",
            "list-tags",
            image_uri,
            f"--filter=tags={raw_version}",
            "--format=json",
        ]
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )
            data = json.loads(res.stdout)
            if data and isinstance(data, list) and len(data) > 0:
                return data[0]
        except Exception as e:
            logger.warning(
                f"Could not resolve tag '{raw_version}' for image '{image_uri}': {e}"
            )
        return None

    def get_git_tag_timestamp(
        self, repo: str, version: str
    ) -> Optional[Tuple[str, str]]:
        """Gets Git commit SHA and ISO timestamp for a git tag via gh api.

        Returns (commit_sha, iso_timestamp) or None.
        """
        tag_name = format_version_tag(version)
        cmd = [
            "gh",
            "api",
            f"repos/{repo}/git/matching-refs/tags/{tag_name}",
            "--jq",
            ".[0].object.sha",
        ]
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )
            sha = res.stdout.strip()
            if not sha:
                return None

            # Fetch commit details to get timestamp
            commit_cmd = [
                "gh",
                "api",
                f"repos/{repo}/commits/{sha}",
                "--jq",
                ".commit.committer.date",
            ]
            commit_res = subprocess.run(
                commit_cmd, capture_output=True, text=True, check=True
            )
            timestamp = commit_res.stdout.strip()
            return sha, timestamp
        except Exception as e:
            logger.warning(
                f"Could not resolve git tag '{tag_name}' for repo '{repo}': {e}"
            )
        return None

    def resolve_component_version(
        self, comp: ComponentConfig, prev_version: str, new_version: str
    ) -> ComponentVersionInfo:
        """Resolves version info (SHAs, timestamps, image URI) for a component."""
        info = ComponentVersionInfo(
            component_id=comp.id,
            component_name=comp.name,
            repo_name=comp.sources[0].repo if comp.sources else "",
            previous_version=prev_version,
            new_version=new_version,
            image_uri=comp.image_uri,
        )

        # 1. Primary image resolution via gcloud container images list-tags
        if comp.image_uri:
            prev_data = self.resolve_image_tag_info(
                comp.image_uri, prev_version
            )
            new_data = self.resolve_image_tag_info(comp.image_uri, new_version)

            if prev_data and "timestamp" in prev_data:
                info.prev_timestamp = prev_data["timestamp"].get("datetime")
                info.previous_sha = prev_data.get("digest")
            if new_data and "timestamp" in new_data:
                info.new_timestamp = new_data["timestamp"].get("datetime")
                info.new_sha = new_data.get("digest")

        # 2. Fallback to Git tag resolution for monorepo or missing image tags
        if not info.prev_timestamp and comp.sources:
            git_prev = self.get_git_tag_timestamp(
                comp.sources[0].repo, prev_version
            )
            if git_prev:
                info.previous_sha, info.prev_timestamp = git_prev

        if not info.new_timestamp and comp.sources:
            git_new = self.get_git_tag_timestamp(
                comp.sources[0].repo, new_version
            )
            if git_new:
                info.new_sha, info.new_timestamp = git_new

        return info

    def fetch_prs_for_date_range(
        self, repo: str, prev_timestamp: str, new_timestamp: str
    ) -> List[PullRequest]:
        """Fetches all merged PRs for a repository between prev_timestamp and new_timestamp in 1 single call.

        Executes `gh pr list --search 'merged:T_prev..T_new base:main'`.
        """
        # Format timestamps for GitHub search API (YYYY-MM-DDTHH:MM:SSZ)
        t_prev = (
            prev_timestamp.split(".")[0].replace(" ", "T")
            if prev_timestamp
            else ""
        )
        t_new = (
            new_timestamp.split(".")[0].replace(" ", "T")
            if new_timestamp
            else ""
        )

        search_query = f"merged:{t_prev}..{t_new} base:main"
        cmd = [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "merged",
            "--search",
            search_query,
            "--json",
            "number,title,body,author,url,labels,files,mergedAt",
            "--limit",
            "200",
        ]

        logger.info(f"Fetching PRs for {repo} with query '{search_query}'...")
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )
            raw_prs = json.loads(res.stdout)
            prs: List[PullRequest] = []
            for item in raw_prs:
                author_login = (
                    item.get("author", {}).get("login", "unknown")
                    if isinstance(item.get("author"), dict)
                    else "unknown"
                )
                labels = [
                    l.get("name", "")
                    for l in item.get("labels", [])
                    if isinstance(l, dict)
                ]
                files = [
                    f.get("path", "")
                    for f in item.get("files", [])
                    if isinstance(f, dict)
                ]

                pr = PullRequest(
                    number=item["number"],
                    title=item.get("title", ""),
                    body=item.get("body", ""),
                    author=author_login,
                    url=item.get("url", ""),
                    merged_at=item.get("mergedAt", ""),
                    repo_name=repo,
                    labels=labels,
                    files_changed=files,
                )
                prs.append(pr)
            return prs
        except Exception as e:
            logger.error(f"Failed to fetch PRs for {repo}: {e}")
            return []

    def is_pr_matching_rule(self, pr: PullRequest, rule: SourceRule) -> bool:
        """Checks if a PR matches a component's SourceRule (repo name and optional path filter)."""
        if pr.repo_name != rule.repo:
            return False

        # If no path filter, match all PRs in that repo
        if not rule.path_filter:
            return True

        # If path filter specified, check if any changed file matches
        path = rule.path_filter.rstrip("/")
        for f in pr.files_changed:
            if f.startswith(path) or f.startswith(f"{path}/"):
                return True
        return False

    def extract(
        self,
        prev_version: str,
        new_version: str,
        additional_instructions: Optional[str] = None,
    ) -> ReleaseInfoManifest:
        """Main entry point: orchestrates tag resolution, date-range PR fetching, and manifest assembly."""
        logger.info(
            f"Starting PR extraction for release range {prev_version} -> {new_version}..."
        )

        manifest = ReleaseInfoManifest(
            previous_version=prev_version,
            new_version=new_version,
            additional_instructions=additional_instructions,
        )

        # 1. Resolve version info and timestamps across all components
        repo_timestamps: Dict[str, List[str]] = {}
        for comp_id, comp in COMPONENTS.items():
            comp_info = self.resolve_component_version(
                comp, prev_version, new_version
            )
            manifest.components[comp_id] = comp_info

            # Track timestamps per repo to compute widest range
            for rule in comp.sources:
                if rule.repo not in repo_timestamps:
                    repo_timestamps[rule.repo] = []
                if comp_info.prev_timestamp:
                    repo_timestamps[rule.repo].append(comp_info.prev_timestamp)
                if comp_info.new_timestamp:
                    repo_timestamps[rule.repo].append(comp_info.new_timestamp)

        # 2. For each repository, compute min & max timestamps and fetch PRs in 1 single call
        raw_prs_by_repo: Dict[str, List[PullRequest]] = {}
        all_prs_set: Dict[Tuple[str, int], PullRequest] = {}

        for repo, ts_list in repo_timestamps.items():
            if not ts_list:
                # Default to fallback timestamp if image tags missing
                t_min = "2026-01-01T00:00:00Z"
                t_max = datetime.utcnow().isoformat() + "Z"
            else:
                sorted_ts = sorted(ts_list)
                t_min = sorted_ts[0]
                t_max = sorted_ts[-1]

            prs = self.fetch_prs_for_date_range(repo, t_min, t_max)
            raw_prs_by_repo[repo] = prs
            for pr in prs:
                all_prs_set[(pr.repo_name, pr.number)] = pr

        # 3. Map PRs to components based on SourceRules
        for comp_id, comp in COMPONENTS.items():
            comp_prs: List[PullRequest] = []
            comp_info = manifest.components.get(comp_id)

            for rule in comp.sources:
                prs_for_repo = raw_prs_by_repo.get(rule.repo, [])
                for pr in prs_for_repo:
                    if self.is_pr_matching_rule(pr, rule):
                        # Add target component tag to PR
                        if comp_id not in pr.target_components:
                            pr.target_components.append(comp_id)
                        if pr not in comp_prs:
                            comp_prs.append(pr)

            manifest.pull_requests_by_component[comp_id] = comp_prs

        manifest.all_pull_requests = list(all_prs_set.values())
        logger.info(
            f"Successfully extracted {len(manifest.all_pull_requests)} unique PRs across {len(manifest.components)} components."
        )
        return manifest
