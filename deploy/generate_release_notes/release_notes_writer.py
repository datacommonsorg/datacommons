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
Your task is to write publication-ready, partner-facing release notes for Data Commons Platform release {manifest.new_version} ({release_date}).

### Core Writing Guidelines & Tone:
1. **Tone & Style**: Write in a clear, positive, partner-facing tone using plain language. Use second person ("You can now...") and active voice for new features and improvements. Use past tense for bug fixes ("Fixed...", "Resolved...").
2. **Target Audience (Building ON TOP OF Platform)**:
   - Write for external developers, data engineers, and instance operators building ON TOP OF Data Commons Platform (NOT internal platform maintainers).
   - Primary Focus: **Ingestion Inputs & Pipelines** (CSV/SDMX inputs, data loading, workflow parameters) and **APIs & Tooling** (REST APIs, SDMX 3.0 endpoints, `/v2/observation`, MCP tools, Web UI, Admin CLI).
3. **De-emphasize Database Layer**:
   - DO NOT focus on Spanner database layer mechanics (e.g. Spanner graph schema, KeyValueStore cutovers, Spanner table internals). Frame changes around how they affect API response speed, data availability, or ingestion inputs!
4. **Strict Exclusions**:
   - DO NOT include internal integration test suites, Spanner Omni test setups, CI sandbox workflows, or developer-only test sample data updates.
   - DO NOT include internal code refactors or unused example file cleanups.
5. **Level of Detail & Use Case Focus**:
   - For major features: Provide an engaging "What's New", "Why it Matters" (business/technical benefit), and a bulleted list under "**Capabilities & Use Cases Enabled**".
   - **DO NOT write a laundry list of code changes or PR descriptions!** Every bullet under Capabilities MUST describe an explicit thing the user can DO (e.g., 'Query bilateral trade flows between two countries', 'Import SDMX 3.0 CSV files directly', 'Run targeted single-entity vs child-place research playbooks'). Focus on supported input types, query capabilities, and real use cases!
   - For single-PR features: Provide rich, self-contained descriptions so partners do not need to look up code diffs.
   - For bug fixes: Focus on what was broken, how it was resolved, and how the system behaves now.
6. **Link Formatting**:
   - Every PR reference MUST be formatted as a clickable Markdown link: `[<repo_short>#<pr_number>](<pr_url>)` (e.g. `[datacommons#188](https://github.com/datacommonsorg/datacommons/pull/188)`).
   - DO NOT put backticks around or inside the link text (e.g. write `[datacommons#188](URL)`, NEVER `[`datacommons#188`](URL)` or `` `[datacommons#188](URL)` ``).
7. **Strict Constraints**:
   - DO NOT use any emojis anywhere in the document.
   - DO NOT include a component version table or git commit/SHA table.
   - DO NOT include release range commit text (e.g., "Release range: v1.1.0 to v1.1.1").
   - Place the 1-2 sentence Executive Summary directly beneath the main title (`# Data Commons Platform Release {manifest.new_version} ({release_date})`).
   - Output ONLY clean, valid GitHub Flavored Markdown (GFM).

---

### Input Release Data:

#### Synthesized Features & Updates:
{json.dumps(features_payload, indent=2)}

#### Bug Fixes & Refactors:
{json.dumps(bug_fixes_payload, indent=2)}

{instructions_context}

---

### Required Output Markdown Structure:

# Data Commons Platform Release {manifest.new_version} ({release_date})

*(1-2 sentences highlighting the most important capabilities, improvements, and fixes in this release for partners and platform operators.)*

---

## Key Feature Updates

*(Group major feature updates here. For each feature, use the following structure:)*

### [Feature Title]
**What's New**: [Clear description of what partners or operators can now do]
**Why it Matters**: [Business benefit and technical impact]
**Capabilities & Use Cases Enabled**:
- [Actionable Use Case / Input Capability 1] ([repo#PR](URL))
- [Actionable Use Case / Input Capability 2] ([repo#PR](URL))

---

## Improvements & Configuration Updates

*(List enhancements, performance updates, or required Terraform/Admin Panel configuration changes as concise bullet points:)*

- **[Improvement Title]**: [Summary of update, configuration instructions if required, and benefit] ([repo#PR](URL))

---

## Bug Fixes

*(List ONLY substantive bug fixes that resolve user-facing errors, data issues, or platform operator failures in past tense. DO NOT include internal dev cleanups, test refactors, or unused example file removals:)*

- **[Component / Scope]**: [Description of what was fixed and how the system behaves now] ([repo#PR](URL))
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
