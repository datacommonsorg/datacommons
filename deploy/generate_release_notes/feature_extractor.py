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

Synthesizes raw PullRequests into structured FeatureUpdate objects using Gemini LLM,
classifying features into standard SOP categories and handling feature grouping.
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

DEFAULT_MODEL = "gemini-3.6-flash"

VALID_SOP_CATEGORIES = {cat.value for cat in SOPCategory}


def detect_internal_regressions(prs: List[PullRequest]) -> Dict[str, str]:
    """Deterministically identifies PRs that fix regressions introduced by earlier PRs in the same release window.

    Returns a dict mapping pr.qualified_id -> parent_feature_pr.qualified_id.
    """
    sorted_prs = sorted(prs, key=lambda p: p.merged_at or "")
    file_to_prs: Dict[str, List[PullRequest]] = {}
    regression_map: Dict[str, str] = {}

    for pr in sorted_prs:
        title_lower = pr.title.lower()
        is_fix = any(
            w in title_lower
            for w in ["fix", "bug", "resolve", "patch", "repair", "correct"]
        )

        if is_fix and pr.files_changed:
            matching_earlier_prs = []
            for f in pr.files_changed:
                if f in file_to_prs:
                    for prev_pr in file_to_prs[f]:
                        if (
                            prev_pr.number != pr.number
                            and prev_pr.repo_name == pr.repo_name
                        ):
                            matching_earlier_prs.append(prev_pr)

            if matching_earlier_prs:
                parent_pr = matching_earlier_prs[-1]
                regression_map[pr.qualified_id] = parent_pr.qualified_id
                logger.info(
                    f"Deterministically detected internal regression: {pr.qualified_id} fixes intermediate PR {parent_pr.qualified_id}"
                )

        for f in pr.files_changed:
            if f not in file_to_prs:
                file_to_prs[f] = []
            file_to_prs[f].append(pr)

    return regression_map


class FeatureExtractor:
    """Single-stage Gemini LLM Pipeline for filtering, classifying, and synthesizing DCP release features."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
        # Backward compatibility aliases
        filter_model: Optional[str] = None,
        synthesis_model: Optional[str] = None,
    ):
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            logger.warning(
                "Neither GEMINI_API_KEY nor GOOGLE_API_KEY set in environment. Gemini API calls will fail if not authenticated via GCP default credentials."
            )
            self.client = genai.Client()
        else:
            self.client = genai.Client(api_key=key)

        self.model_name = synthesis_model or model_name or DEFAULT_MODEL

    def extract_features(
        self,
        manifest: ReleaseInfoManifest,
        additional_instructions: Optional[str] = None,
    ) -> List[FeatureUpdate]:
        """Classifies, groups, and synthesizes raw PRs into FeatureUpdate objects in 1 Gemini call."""
        if not manifest.all_pull_requests:
            logger.warning("No PRs provided in manifest for feature extraction.")
            return []

        logger.info(
            f"Step 2: Extracting features from {len(manifest.all_pull_requests)} PRs using {self.model_name}..."
        )

        # Pre-process PRs to deterministically detect internal regressions within this release window
        regression_map = detect_internal_regressions(manifest.all_pull_requests)

        # Build detailed PR context for model with merged_at timestamps and qualified IDs
        detailed_prs = []
        for pr in manifest.all_pull_requests:
            # Preserve "BREAKING CHANGE:" sections if present in body
            body_text = pr.body or ""
            body_snippet = body_text[:500]
            if "BREAKING CHANGE" in body_text and "BREAKING CHANGE" not in body_snippet:
                bc_start = body_text.find("BREAKING CHANGE")
                body_snippet += "\n...\n" + body_text[bc_start : bc_start + 300]

            pr_dict = {
                "id": pr.qualified_id,
                "title": pr.title,
                "author": pr.author,
                "repo": pr.repo_name,
                "url": pr.url,
                "merged_at": pr.merged_at,
                "target_components": pr.target_components,
                "files_changed": pr.files_changed[:10],
                "body_summary": body_snippet,
                "is_internal_regression": pr.qualified_id in regression_map,
                "fixes_intermediate_pr": regression_map.get(pr.qualified_id),
            }
            detailed_prs.append(pr_dict)

        instructions_context = ""
        if additional_instructions or manifest.additional_instructions:
            instructions_text = additional_instructions or manifest.additional_instructions
            instructions_context = (
                f"\n### Additional User Context & High-Priority Highlights:\n"
                f"Note: User instructions have top priority and override default classification or filtering where applicable:\n"
                f"{instructions_text}\n"
            )

        prompt = f"""You are an expert Technical Release Manager for the Data Commons Platform (DCP). Your task is to analyze raw PR metadata and draft structured, user-centric release notes for version `{manifest.new_version}` (previous version: `{manifest.previous_version}`).

---

### 1. CONTEXT & DOMAIN KNOWLEDGE
Data Commons Platform (DCP) is a self-hosted, Cloud Spanner-backed deployment of Data Commons. It replaces legacy Bigtable with Cloud Spanner graph tables and vector embeddings. It features custom data ingestion pipelines, specialized serving APIs, and deployment automation across 6 repositories:
1. `datacommonsorg/datacommons` (Monorepo): Terraform modules (`infra/dcp/`, `infra/modules/`), CLI tools (`packages/datacommons-cli/`), and Admin Portal (`packages/datacommons-admin/`).
2. `datacommonsorg/website`: Web application serving UI and APIs (`server/`, `static/`, `build/cdc_services/`, `build/cdc_data/`).
3. `datacommonsorg/mixer`: Core Spanner gRPC graph, StatVar serving engine, and ESPv2 gateway (`internal/server/`, `proto/`, `deploy/helm_charts/`).
4. `datacommonsorg/import`: Data processing pipelines (`simple/`, `pipeline/ingestion/` Dataflow Java worker, `pipeline/workflow/ingestion-helper/`, `pipeline/workflow/aggregation-helper/`).
5. `datacommonsorg/agent-toolkit`: Datacommons Model Context Protocol (MCP) server and tools (`src/datacommons_mcp/`).
6. `datacommonsorg/datacommons-data`: Data preprocessor container image built from `import/simple/` and `website/build/cdc_data/`.

---

### 2. CLASSIFICATION RULES (SOP CATEGORIES)
Categorize EVERY valid feature into EXACTLY ONE of these 4 categories based on its files and description:
* **"Spanner Graph & APIs"**: Features touching SDMX 3.0 REST endpoints, ESPv2 query parameter handling, `/v2/observation` StatVar data retrieval, Spanner gRPC graph serving, `proto/` definitions, or `agent-toolkit` MCP server/tools.
* **"Ingestion & Safety"**: Features touching Dataflow Java worker (`pipeline/ingestion/`), `ingestion-helper`, `aggregation-helper`, Spanner table loading, timestamp bounds, data validation, or health probes.
* **"Search & Website"**: Features touching Spanner vector embeddings (`NodeEmbedding`), private instance `detect-and-fulfill`, Nginx/Envoy, Website UI, or Admin Portal UI.
* **"Infra & Tooling"**: Features touching `infra/dcp/` (Terraform), `datacommons-cli`/`admin` PyPI packages, monorepo root configs, or Cloud Build release pipelines.

---

### 3. STRICT FILTERING & DEDUPLICATION RULES
* **EXCLUDE Internal Dev & Testing PRs**: 
  * Ignore automated bot PRs (e.g., Dependabot, Renovate, "chore: bump version").
  * Ignore all test-only PRs (e.g., integration test setups, Spanner Omni test conversions, CI sandbox workflows, local test harnesses, hermetic test refactors, and test-only sample data updates like OECD wage sample data).
  * Ignore formatting, typos, or non-informative refactors with zero user impact.
* **EXCLUDE Internal Iteration Bug Fixes (Release Window Regressions)**:
  * If a bug fix PR addresses a bug or regression introduced *within this same release window* (i.e. introduced after `{manifest.previous_version}` and fixed before `{manifest.new_version}`), DO NOT list it as a standalone Bug Fix!
  * Fold it into the parent `FeatureUpdate` as part of that feature's development, or drop it if it was just an internal dev fix.
  * ONLY list bugs under 'Bug Fixes' if the bug was present in `{manifest.previous_version}` or an earlier published release!
* **Deduplicate & Group Related PRs**: 
  * Combine related PRs (e.g., an initial feature PR + follow-up bug fixes + post-feature adjustments) into a SINGLE cohesive `FeatureUpdate`.
  * If PRs conflict or supersede each other, describe ONLY the final chronological state at `{manifest.new_version}`.

---

### 4. WRITING STYLE & PERSONA FOCUS (CONCISE & ANTI-FLUFF)
* **Target Audience**: Write for platform users, data engineers, API consumers, and instance operators building ON TOP of DCP.
* **BANNED AI FLUFF WORDS (STRICT)**: DO NOT use AI cliché words: `seamlessly`, `empower`, `leveraging`, `robust`, `overhaul`, `delivers a major`, `comprehensive`, `fosters`, `game-changing`, `cutting-edge`, `paradigm`. Write simple, direct sentences instead!
* **Concise Sentence Budget**: Keep `description` to 1-2 punchy sentences (max 25 words). Keep `pr_contributions` summaries to 1 short sentence (12-15 words max per PR).
* **User Capability Focus**: Frame the "description" and "pr_contributions" around what the user can *actually do* or what *input formats* are now supported (e.g., "Configure max_workers in Terraform to scale Dataflow workers automatically" instead of "Added Terraform max_workers variable").
* **De-emphasize DB Internals**: Minimize mentions of Spanner database internals (e.g., Spanner graph schema, KeyValueStore cutover). Focus instead on the user-facing API or Ingestion behavior change.

---

### 5. INPUT DATA
* **Instructions Context**: 
{instructions_context}
* **Raw Merged PRs**: 
{json.dumps(detailed_prs, indent=2)}

---

### 6. OUTPUT FORMAT
Respond ONLY with a valid JSON array of `FeatureUpdate` objects conforming strictly to the schema below. 
Do not include markdown code block formatting (such as ```json) or any conversational text before or after the JSON. Output raw JSON only.

[
  {{
    "id": "short_unique_snake_case_id",
    "title": "Clear Technical Feature Title",
    "description": "2-3 sentence technical description of the feature, explaining the change and its user-facing impact.",
    "category": "Spanner Graph & APIs | Ingestion & Safety | Search & Website | Infra & Tooling",
    "target_components": ["dcp", "services", "preprocessing", "dataflow_worker", "ingestion_helper", "postprocessing"],
    "included_prs": ["agent-toolkit#211", "datacommons#189"],
    "pr_contributions": {{
      "agent-toolkit#211": "Query bilateral trade and migration relationships between multiple entities",
      "datacommons#189": "Configure max_workers in Terraform to scale Dataflow workers automatically for large imports"
    }},
    "is_dcp_relevant": true,
    "breaking_changes": "Detailed description of the breaking change if any, otherwise null"
  }}
]
"""

        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            )
            res = self.client.models.generate_content(
                model=self.model_name,
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
                f"Step 2 Complete: Synthesized {len(features)} structured FeatureUpdate objects across categories."
            )
            return features
        except Exception as e:
            logger.error(f"Step 2 Feature extraction failed: {e}")
            raise RuntimeError(f"Failed to extract release features with Gemini: {e}")
