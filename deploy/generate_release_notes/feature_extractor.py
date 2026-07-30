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

        # Build detailed PR context for model with merged_at timestamps and qualified IDs
        detailed_prs = []
        for pr in manifest.all_pull_requests:
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

        prompt = f"""You are an expert Technical Release Manager for Data Commons Platform (DCP) drafting official release notes for release {manifest.new_version} (previous version: {manifest.previous_version}).

### Context & Domain Knowledge — What is Data Commons Platform (DCP)?
Data Commons Platform (DCP) is a self-hosted, Cloud Spanner-backed deployment of Data Commons. It replaces legacy Bigtable with Cloud Spanner graph tables and vector embeddings, featuring custom data ingestion pipelines, specialized serving APIs, and deployment automation across 6 key repositories:

1. **`datacommonsorg/datacommons` (Monorepo)**:
   - Contains DCP Terraform modules (`infra/dcp/`, `infra/modules/`), CLI tools (`packages/datacommons-cli/`), and Admin Portal (`packages/datacommons-admin/`).
2. **`datacommonsorg/website`**:
   - Web application serving UI and APIs (`server/`, `static/`, `build/cdc_services/`, `build/cdc_data/`).
3. **`datacommonsorg/mixer`**:
   - Core Spanner gRPC graph and StatVar serving engine (`internal/server/`, `proto/`).
4. **`datacommonsorg/import`**:
   - Data processing pipelines: Simple importer (`simple/`), Dataflow Java worker (`pipeline/ingestion/`), Ingestion Helper (`pipeline/workflow/ingestion-helper/`), Aggregation Helper (`pipeline/workflow/aggregation-helper/`).
5. **`datacommonsorg/agent-toolkit`**:
   - Datacommons Model Context Protocol (MCP) server and tools (`src/datacommons_mcp/`).
6. **`datacommonsorg/datacommons-data`**:
   - Data preprocessor container image built from `import/simple/` and `website/build/cdc_data/`.

---

### Classification Rules & SOP Categories:
Categorize EVERY feature into EXACTLY ONE of these 4 standard SOP categories based on its files and description:

1. **"Spanner Graph & APIs"**:
   - Features touching SDMX 3.0 REST endpoints, `/v2/observation` StatVar data retrieval, Spanner gRPC graph serving, `proto/` definitions, or `agent-toolkit` MCP server/tools.
2. **"Ingestion & Safety"**:
   - Features touching Dataflow Java worker (`pipeline/ingestion/`), `ingestion-helper`, `aggregation-helper`, Spanner table loading, timestamp bounds, data validation, or health probes.
3. **"Search & Website"**:
   - Features touching Spanner vector embeddings (`NodeEmbedding`), private instance `detect-and-fulfill`, Nginx/Envoy, Website UI, or Admin Portal UI.
4. **"Infra & Tooling"**:
   - Features touching `infra/dcp/` (Terraform), `datacommons-cli`/`admin` PyPI packages, monorepo root configs, or Cloud Build release pipelines.

---

### Task Instructions:
1. **Filter Out & Ignore Internal Dev & Testing PRs (STRICT)**:
   - Completely IGNORE automated bot PRs (e.g. dependabot, renovate, 'chore: bump version to 1.1.1').
   - Completely IGNORE all test-only PRs: integration test setups, Spanner Omni test conversions, CI sandbox workflows, local test harnesses, hermetic test refactors, and test-only sample data updates (e.g. OECD wage sample data). DO NOT output any FeatureUpdate for test-only PRs!
   - Completely IGNORE trivial formatting, typo fixes, or non-informative refactors with zero user impact.

2. **User Persona Focus (Building ON TOP OF Platform)**:
   - Write for people **building ON TOP OF the platform** (data engineers, API consumers, instance operators).
   - Focus on **Ingestion Inputs & Pipelines** (CSV/SDMX inputs, import workflows, validation rules) and **APIs & Tooling** (REST APIs, SDMX 3.0 endpoints, `/v2/observation`, MCP tools, Web UI, Admin CLI).
   - **De-emphasize Database Layer Details**: Minimize mentions of Spanner database internals (e.g. Spanner graph schema, KeyValueStore cutover). Focus instead on the user-facing API or Ingestion behavior change.

3. **Feature Grouping & Deduplication**:
   - Combine related PRs (e.g., an initial feature PR + follow-up bug fixes + test PRs) into a SINGLE cohesive `FeatureUpdate`.
   - List all included PR qualified IDs in `included_prs` (e.g. `["datacommons#188", "datacommons#189"]`).

4. **Supersede Resolution & Chronology**:
   - Use `merged_at` timestamps to understand commit order.
   - If a PR was superseded or modified by a later PR in this release, describe only the FINAL state at {manifest.new_version}.

5. **Actionable Per-PR Capability & Use Case Summaries**:
   - For EVERY PR listed in `included_prs`, provide a specific 1-2 sentence summary under `pr_contributions` describing an **explicit thing the user can DO or input format supported** because of this PR (e.g., `{{"agent-toolkit#211": "Query bilateral trade and migration relationships between multiple entities", "datacommons#189": "Configure max_workers in Terraform to scale Dataflow workers automatically for large imports"}}`). DO NOT list internal code refactors!

{instructions_context}

### Raw Merged PRs:
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
      "agent-toolkit#211": "Query bilateral trade and migration relationships between multiple entities",
      "datacommons#189": "Configure max_workers in Terraform to scale Dataflow workers automatically for large imports"
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
