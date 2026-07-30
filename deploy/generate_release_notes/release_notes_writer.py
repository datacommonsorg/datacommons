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

"""Step 3: Release Notes Writer for Data Commons Platform (DCP) release notes generation.

Uses an Agentic Writer (Gemini Pro) to generate clean, partner-facing, non-technical
release notes following the streamlined Data Commons Platform format.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from deploy.generate_release_notes.models import (
    FeatureUpdate,
    PullRequest,
    ReleaseInfoManifest,
)

logger = logging.getLogger(__name__)

DEFAULT_WRITER_MODEL = "gemini-3.6-flash"


class ReleaseNotesWriter:
    """Agentic Release Notes Writer powered by Gemini Pro."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_WRITER_MODEL,
        include_audit_log: bool = False,
    ):
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            logger.warning(
                "Neither GEMINI_API_KEY nor GOOGLE_API_KEY set in environment. Gemini API calls will fail if not authenticated via GCP default credentials."
            )
            self.client = genai.Client()
        else:
            self.client = genai.Client(api_key=key)

        self.model_name = model_name
        self.include_audit_log = include_audit_log

    def _extract_bug_fixes(
        self, manifest: ReleaseInfoManifest, features: List[FeatureUpdate]
    ) -> List[Dict[str, Any]]:
        """Extracts PRs that are bug fixes or one-off improvements not covered in major features."""
        included_pr_ids = set()
        for feat in features:
            included_pr_ids.update(feat.included_prs)

        bug_fix_prs = []
        for pr in manifest.all_pull_requests:
            if pr.qualified_id in included_pr_ids:
                continue

            title_lower = pr.title.lower()
            # Identify bug fixes or minor partner-relevant PRs
            is_fix = (
                "fix" in title_lower
                or "bug" in title_lower
                or "resolve" in title_lower
                or "correct" in title_lower
                or "patch" in title_lower
            )
            is_bot = (
                "bump version" in title_lower
                or pr.author == "datacommons-robot-author"
                or "dependabot" in pr.author.lower()
                or "renovate" in pr.author.lower()
            )

            if is_fix and not is_bot:
                bug_fix_prs.append(
                    {
                        "id": pr.qualified_id,
                        "title": pr.title,
                        "author": pr.author,
                        "repo": pr.repo_name,
                        "url": pr.url,
                        "body_snippet": pr.body[:300] if pr.body else "",
                    }
                )

        return bug_fix_prs

    def build_audit_table_markdown(
        self, manifest: ReleaseInfoManifest, features: List[FeatureUpdate]
    ) -> str:
        """Generates an optional Markdown audit table listing all raw PRs and their status."""
        feature_pr_map: Dict[str, FeatureUpdate] = {}
        for feat in features:
            for pr_id in feat.included_prs:
                feature_pr_map[pr_id] = feat

        rows = []
        for pr in manifest.all_pull_requests:
            repo_short = pr.repo_name.split("/")[-1]
            title_sanitized = pr.title.replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")

            if pr.qualified_id in feature_pr_map:
                feat = feature_pr_map[pr.qualified_id]
                status = "Substantive Feature" if feat.is_dcp_relevant else "Base DC Only"
                category = feat.category
            elif "bump version" in pr.title.lower() or "bot" in pr.author.lower():
                status = "Bot Version Bump"
                category = "Infra & Tooling"
            else:
                status = "Refactor / Minor"
                category = "Infra & Tooling"

            components_str = ", ".join(pr.target_components) if pr.target_components else "infra"
            rows.append(
                f"| `{repo_short}` | [{pr.number}]({pr.url}) | {title_sanitized} | @{pr.author} | {components_str} | {category} | {status} |"
            )

        header = (
            "\n---\n\n## Complete Release Audit Log\n\n"
            "| Repo | PR # | Title | Author | Components | Category / Type | Status |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        )
        return header + "\n".join(rows) + "\n"

    def render(
        self,
        manifest: ReleaseInfoManifest,
        features: List[FeatureUpdate],
        additional_instructions: Optional[str] = None,
        release_date: str = "2026-07-29",
    ) -> str:
        """Calls Gemini Pro to generate publication-ready Markdown release notes according to the streamlined template."""
        logger.info(
            f"Step 3: Rendering release notes for {manifest.new_version} using {self.model_name}..."
        )

        # Build payloads for prompt — include ONLY DCP-relevant user/partner features
        features_payload = []
        for feat in features:
            if not feat.is_dcp_relevant:
                logger.info(f"Omitting non-DCP-relevant feature from release notes: {feat.title}")
                continue
            features_payload.append(
                {
                    "id": feat.id,
                    "title": feat.title,
                    "description": feat.description,
                    "category": feat.category,
                    "target_components": feat.target_components,
                    "included_prs": feat.included_prs,
                    "pr_contributions": feat.pr_contributions,
                    "is_dcp_relevant": feat.is_dcp_relevant,
                    "breaking_changes": feat.breaking_changes,
                }
            )

        bug_fixes_payload = self._extract_bug_fixes(manifest, features)

        instructions_context = ""
        if additional_instructions or manifest.additional_instructions:
            instructions_text = additional_instructions or manifest.additional_instructions
            instructions_context = (
                f"\n#### Additional User Instructions & High-Priority Highlights:\n"
                f"{instructions_text}\n"
            )

        prompt = f"""You are an expert Technical Release Manager and Product Documentation Specialist for the Data Commons Platform (DCP). 

Your objective is to generate publication-ready, partner-facing release notes for DCP version `{manifest.new_version}` ({release_date}) using GFM (GitHub Flavored Markdown).

---

### 1. CORE WRITING STYLE & TONE (CONCISE & ANTI-FLUFF)
* **Perspective & Tone**: Write like a senior Google engineer writing a concise technical changelog — direct, factual, punchy, and zero fluff. Use active voice ("You can now...") for features, past tense ("Fixed...") for bugs.
* **Audience Focus**: Write specifically for external developers, data engineers, and instance operators building ON TOP OF the platform. 
* **BANNED AI FLUFF WORDS (STRICT)**: DO NOT use AI cliché words: `seamlessly`, `empower`, `leveraging`, `robust`, `overhaul`, `delivers a major`, `comprehensive`, `fosters`, `game-changing`, `cutting-edge`, `paradigm`. Write simple, direct sentences instead!
* **STRICT WORD COUNT BUDGETS**:
    * **Executive Summary**: Maximum 25 words (1 single, punchy sentence).
    * **What's New**: 15-20 words max (1 direct sentence).
    * **Why it Matters**: 15-20 words max (1 direct sentence).
    * **Capabilities & Changes Bullets**: 12-15 words max per bullet.
* **The "So What?" Rule**: Do not just list code changes. Frame every update around user capability (e.g., *what* can the developer do now, *which* inputs are accepted, or *how* does this affect query performance/scalability?).
* **De-emphasize DB Internals**: Do not write about Spanner database mechanics (e.g., "Spanner graph schema modifications," "KeyValueStore cutovers," or Spanner internal table indexing). Instead, frame these improvements around API response speed, easier configuration, or expanded data ingestion inputs.

---

### 2. STRICT CONSTRAINTS (ZERO-TOLERANCE RULES)
* **NO Emojis**: Do not use emojis anywhere in the document.
* **NO Version/Commit Tables**: Do not include a component version table, git commit hashes, or SHA tables.
* **NO Commit Range Text**: Do not include text like "Release range: v1.1.0 to v1.1.1".
* **NO Code-Fenced Links**: Every PR reference MUST be a clean, clickable GFM link. Do not wrap backticks around or inside link text.
    * **CORRECT**: `[website#123](https://github.com/...)`
    * **INCORRECT**: `[`website#123`](https://github.com/...)` or `[`website#123` (https://github.com/...)]`

---

### 3. INPUT MAPPING RULES (RENDER ALL FEATURES)
You will process two payload inputs. Map them to the final release note sections as follows:

1.  **`features_payload`**: 
    *   **STRICT REQUIREMENT**: You MUST render EVERY item provided in `features_payload`. DO NOT drop or omit any feature!
    *   Major, highly impactful items (e.g. SDMX 3.0 REST Endpoints, Agent MCP Toolkit Overhaul, Modular Ingestion Workflows) MUST be rendered as detailed feature sections under **Key Feature Updates**.
    *   Minor enhancements, optimizations, or configuration instructions must be formatted as concise bullet points under **Improvements & Configuration Updates**.
2.  **`bug_fixes_payload`**: 
    *   Substantive bug fixes that address user-facing errors, data inaccuracies, or platform operator crashes must be mapped to **Bug Fixes**.
    *   *STRICT EXCLUSION*: Completely ignore internal development chores, test refactors, CI sandbox workflows, local test setups, or unused sample data removals.

---

### 4. DO vs. DON'T CONTENT SAMPLES

| Section | ❌ DO NOT Write (Internal Developer Focus) |  DO Write (Partner & Operator Focus) |
| :--- | :--- | :--- |
| **Key Features** | "Merged PR to implement SDMX 3.0 CSV parser in import repo." | **Import SDMX 3.0 CSV files directly** to ingest standard-compliant macroeconomic datasets into your private instance with zero manual preprocessing. |
| **Improvements** | "Added Terraform variable max_workers." | **Scalable Dataflow Import Pipelines**: Configure `max_workers` in your Terraform configurations to scale compute resources automatically during large-scale imports. |
| **Improvements** | "Propagated V2_RESOLVE_INDICATORS_TARGET to website." | **Filter Website Explore to Custom Variables**: Set `datacommons_services_website_search_scope` to `custom_only` in Terraform to restrict website search and explore results strictly to your instance's custom variables. |
| **Bug Fixes** | "Fixed NullPointerException in observation API when entity is empty." | **Observation Serving**: Resolved a crash in the `/v2/observation` endpoint when querying empty entities; the API now gracefully returns an empty payload with a 200 OK. |

---

### 5. INPUT DATA

#### Major Features & Updates:
{json.dumps(features_payload, indent=2)}

#### Bug Fixes & Refactors:
{json.dumps(bug_fixes_payload, indent=2)}

{instructions_context}

---

### 6. REQUIRED OUTPUT STRUCTURE
Generate GFM matching the exact structure below. Do not add any greeting, intro, or concluding conversational text outside this structure.

# Data Commons Platform Release {manifest.new_version} ({release_date})

[Provide a high-impact, 1-2 sentence Executive Summary highlighting the most important capabilities, performance boosts, and critical fixes introduced in this release for partners and platform operators.]

---

## Key Feature Updates

### [Feature Title]

**What's New**: [Clear description of what partners or operators can now do]

**Why it Matters**: [Business benefit, technical impact, or performance advantage]

**Capabilities & Use Cases Enabled**:
- [Actionable Use Case / Input Capability 1] ([repo_short#PR](URL))
- [Actionable Use Case / Input Capability 2] ([repo_short#PR](URL))

---

## Improvements & Configuration Updates

- **[Improvement Title]**: [Summary of update, step-by-step configuration instructions if required, and direct benefit] ([repo_short#PR](URL))

---

## Bug Fixes

- **[Component / Scope]**: [Description of what was broken, how it was resolved, and how the system behaves now] ([repo_short#PR](URL))
"""

        try:
            config = types.GenerateContentConfig(
                temperature=0.2,
            )
            res = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            markdown_content = res.text.strip()

            # Append optional audit table if requested
            if self.include_audit_log:
                audit_table_md = self.build_audit_table_markdown(manifest, features)
                markdown_content += "\n" + audit_table_md

            logger.info("Step 3 Complete: Release notes successfully generated.")
            return markdown_content
        except Exception as e:
            logger.error(f"Step 3 Release Notes Writer failed with Gemini Pro: {e}")
            raise RuntimeError(f"Failed to generate release notes with Gemini Pro: {e}")
