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

"""Step 2: Feature Extractor for Data Commons Platform (DCP) release notes generation.

Executes a Two-Stage Gemini LLM Pipeline (Flash + Pro) for noise filtering,
SOP classification, feature grouping, and technical release notes synthesis.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Any

from google import genai
from google.genai import types

from deploy.generate_release_notes.models import (
    FeatureUpdate,
    PullRequest,
    ReleaseInfoManifest,
    SOPCategory,
)

logger = logging.getLogger(__name__)

DEFAULT_FILTER_MODEL = "gemini-2.5-flash"
DEFAULT_SYNTHESIS_MODEL = "gemini-2.5-pro"

VALID_SOP_CATEGORIES = {cat.value for cat in SOPCategory}


class FeatureExtractor:
    """Two-Stage Gemini LLM Pipeline for filtering, classifying, and synthesizing DCP release features."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        filter_model: str = DEFAULT_FILTER_MODEL,
        synthesis_model: str = DEFAULT_SYNTHESIS_MODEL,
    ):
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            logger.warning(
                "Neither GEMINI_API_KEY nor GOOGLE_API_KEY set in environment. Gemini API calls will fail if not authenticated via GCP default credentials."
            )
            self.client = genai.Client()
        else:
            self.client = genai.Client(api_key=key)

        self.filter_model = filter_model
        self.synthesis_model = synthesis_model

    def filter_prs_with_flash(self, manifest: ReleaseInfoManifest) -> List[PullRequest]:
        """Stage 1 (Flash Model): Rapidly triages all raw PRs to weed out bot bumps, typo fixes, and non-informative noise."""
        if not manifest.all_pull_requests:
            logger.warning("No PRs provided in manifest for Stage 1 filtering.")
            return []

        logger.info(
            f"Stage 1: Filtering {len(manifest.all_pull_requests)} raw PRs using {self.filter_model}..."
        )

        # Build compact representation for Flash model using qualified PR IDs (e.g. 'datacommons#188')
        pr_summaries = []
        for pr in manifest.all_pull_requests:
            pr_summaries.append(
                {
                    "id": pr.qualified_id,
                    "title": pr.title,
                    "repo": pr.repo_name,
                    "author": pr.author,
                    "files_changed_count": len(pr.files_changed),
                    "sample_files": pr.files_changed[:10],
                }
            )

        prompt = f"""You are a Senior Technical Release Engineer for Data Commons Platform (DCP).
Analyze the following list of merged Pull Requests for release range {manifest.previous_version} -> {manifest.new_version}.

Goal: Identify all SUBSTANTIVE, meaningful Pull Requests that represent feature additions, bug fixes, infrastructure changes, configuration updates, or Data Commons Platform/Base capabilities.

Filter OUT ONLY non-informative noise:
- Automated bot version bumps (e.g., 'chore: bump version to 1.1.1', dependabot, renovate).
- Trivial formatting, linting, or typo fixes in documentation/README (e.g., 'fix typo in README').
- Trivial internal test-only refactors with zero functional impact.

DO NOT filter out base Data Commons features or infrastructure PRs — keep all substantive PRs!

Here is the list of PRs:
{json.dumps(pr_summaries, indent=2)}

Respond ONLY with a JSON object containing a single key "relevant_pr_ids" with an array of qualified PR ID strings (e.g., ["datacommons#188", "import#42"]).
Example: {{"relevant_pr_ids": ["datacommons#188", "import#42"]}}
"""

        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            )
            res = self.client.models.generate_content(
                model=self.filter_model,
                contents=prompt,
                config=config,
            )
            data = json.loads(res.text)
            relevant_ids = set(data.get("relevant_pr_ids", []))
            
            candidate_prs = [
                pr for pr in manifest.all_pull_requests if pr.qualified_id in relevant_ids
            ]
            logger.info(
                f"Stage 1 Complete: Retained {len(candidate_prs)} / {len(manifest.all_pull_requests)} substantive PRs."
            )
            return candidate_prs
        except Exception as e:
            logger.error(f"Stage 1 Flash filtering failed: {e}. Falling back to all non-bot PRs.")
            # Basic fallback for error resilience
            return [
                pr for pr in manifest.all_pull_requests 
                if "bump version" not in pr.title.lower() and pr.author != "datacommons-robot-author"
            ]

    def synthesize_features_with_pro(
        self,
        manifest: ReleaseInfoManifest,
        candidate_prs: List[PullRequest],
        additional_instructions: Optional[str] = None,
    ) -> List[FeatureUpdate]:
        """Stage 2 (Pro Model): Performs deep semantic classification, feature grouping, override resolution, and SOP drafting."""
        if not candidate_prs:
            logger.warning("No candidate PRs provided for Stage 2 synthesis.")
            return []

        logger.info(
            f"Stage 2: Synthesizing features from {len(candidate_prs)} candidate PRs using {self.synthesis_model}..."
        )

        # Build detailed PR context for Pro model with merged_at timestamps and qualified IDs
        detailed_prs = []
        for pr in candidate_prs:
            # Preserve "BREAKING CHANGE:" sections if present in body
            body_text = pr.body or ""
            body_snippet = body_text[:500]
            if "BREAKING CHANGE" in body_text and "BREAKING CHANGE" not in body_snippet:
                bc_start = body_text.find("BREAKING CHANGE")
                body_snippet += "\n...\n" + body_text[bc_start : bc_start + 300]

            detailed_prs.append(
                {
                    "id": pr.qualified_id,
                    "title": pr.title,
                    "author": pr.author,
                    "repo": pr.repo_name,
                    "url": pr.url,
                    "merged_at": pr.merged_at,
                    "target_components": pr.target_components,
                    "files_changed": pr.files_changed[:10],
                    "body_summary": body_snippet,
                }
            )

        instructions_context = ""
        if additional_instructions or manifest.additional_instructions:
            instructions_text = additional_instructions or manifest.additional_instructions
            instructions_context = (
                f"\n### Additional User Context & High-Priority Highlights:\n"
                f"Note: User instructions have top priority and override default classification or filtering where applicable:\n"
                f"{instructions_text}\n"
            )

        prompt = f"""You are an expert Technical Release Manager drafting official release notes for Data Commons Platform (DCP) release {manifest.new_version} (previous version: {manifest.previous_version}).

### Task Instructions:
1. **Semantic Classification**: Categorize each feature into EXACTLY ONE of the 4 standard DCP SOP categories (use exact category names):
   - "Spanner Graph & APIs" (SDMX 3.0 REST API, `/v2/observation` StatVars, MCP server/tools, Spanner gRPC serving/protos)
   - "Ingestion & Safety" (Ingestion Helper, Aggregation Helper, Dataflow Java worker, timestamp bounds, safety checks, Spanner loading)
   - "Search & Website" (Spanner vector embeddings / `NodeEmbedding`, private instance `detect-and-fulfill`, Website UI, Nginx/Envoy)
   - "Infra & Tooling" (DCP Terraform modules, `datacommons admin`/`cli` PyPI packages, monorepo packages, Cloud Build release pipelines)

2. **Feature Grouping & Deduplication**:
   - Combine related PRs (e.g., an initial feature PR + follow-up bug fixes + test PRs) into a SINGLE cohesive `FeatureUpdate`.
   - List all included PR qualified IDs in `included_prs` (e.g. `["datacommons#188", "datacommons#189"]`).

3. **Supersede Resolution & Chronology**:
   - Use the `merged_at` timestamps to understand commit order.
   - If a PR was superseded or modified by a later PR in this release, describe only the FINAL state at {manifest.new_version}.

4. **Technical Writing & Comprehensive Context**:
   - Write clear, concise, engineer-style titles and descriptions. Avoid marketing fluff or non-technical summaries.
   - Set `is_dcp_relevant: true` for all platform-relevant features, or `false` for base-only features.
   - If a feature contains only ONE PR, ensure the `description` is rich and comprehensive enough for release notes generation to understand all capabilities implemented.

5. **Per-PR Contribution Summaries**:
   - For EVERY PR listed in `included_prs`, provide a specific 1-2 sentence contribution summary under `pr_contributions` mapping the qualified PR ID to its specific capability contribution (e.g., `{{"datacommons#188": "Removed premature success status set at end of dataflow stage", "datacommons#189": "Added max_workers Terraform variable for Dataflow auto-scaling"}}`).

{instructions_context}

### Substantive Candidate PRs:
{json.dumps(detailed_prs, indent=2)}

Respond ONLY with a JSON array of FeatureUpdate objects with the following schema:
[
  {{
    "id": "short_unique_snake_case_id",
    "title": "Clear Technical Feature Title",
    "description": "2-3 sentence technical description of the feature, changes, and impact.",
    "category": "Spanner Graph & APIs | Ingestion & Safety | Search & Website | Infra & Tooling",
    "target_components": ["dcp", "services", "preprocessing", "dataflow_worker", "ingestion_helper", "postprocessing"],
    "included_prs": ["datacommons#188", "datacommons#189"],
    "pr_contributions": {{
      "datacommons#188": "Removed premature success status set at end of dataflow stage",
      "datacommons#189": "Added max_workers Terraform variable for Dataflow auto-scaling"
    }},
    "is_dcp_relevant": true,
    "breaking_changes": "Optional string describing breaking change if any, else null"
  }}
]
"""

        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            )
            res = self.client.models.generate_content(
                model=self.synthesis_model,
                contents=prompt,
                config=config,
            )
            raw_features = json.loads(res.text)
            features: List[FeatureUpdate] = []
            for item in raw_features:
                cat = item.get("category", "Infra & Tooling")
                if cat not in VALID_SOP_CATEGORIES:
                    # Fuzzy match or fallback to Infra & Tooling
                    matched = False
                    for valid_cat in VALID_SOP_CATEGORIES:
                        if valid_cat.lower() in cat.lower() or cat.lower() in valid_cat.lower():
                            cat = valid_cat
                            matched = True
                            break
                    if not matched:
                        cat = SOPCategory.INFRA_TOOLING.value

                feature = FeatureUpdate(
                    id=item.get("id", f"feature_{len(features)+1}"),
                    title=item.get("title", "Untitled Feature"),
                    description=item.get("description", ""),
                    category=cat,
                    target_components=item.get("target_components", []),
                    included_prs=item.get("included_prs", []),
                    pr_contributions=item.get("pr_contributions", {}),
                    is_dcp_relevant=item.get("is_dcp_relevant", True),
                    breaking_changes=item.get("breaking_changes"),
                )
                features.append(feature)

            logger.info(
                f"Stage 2 Complete: Synthesized {len(features)} structured FeatureUpdate objects across categories."
            )
            return features
        except Exception as e:
            logger.error(f"Stage 2 Pro synthesis failed: {e}")
            raise RuntimeError(f"Failed to synthesize release features with Gemini Pro: {e}")

    def extract_features(
        self,
        manifest: ReleaseInfoManifest,
        additional_instructions: Optional[str] = None,
    ) -> List[FeatureUpdate]:
        """Main entry point: orchestrates Stage 1 Flash filtering -> Stage 2 Pro synthesis -> List[FeatureUpdate]."""
        logger.info(
            f"Starting Step 2 Feature Extraction for release {manifest.previous_version} -> {manifest.new_version}..."
        )

        # Stage 1: Fast Flash Noise Filter
        candidate_prs = self.filter_prs_with_flash(manifest)

        # Stage 2: Deep Pro Synthesis & SOP Classification
        features = self.synthesize_features_with_pro(
            manifest=manifest,
            candidate_prs=candidate_prs,
            additional_instructions=additional_instructions,
        )

        return features
