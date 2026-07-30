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

"""Unit and Integration tests for Release Notes Writer (deploy/generate_release_notes/release_notes_writer.py)."""

import json
import os
from unittest.mock import MagicMock, patch
import pytest

from deploy.generate_release_notes.models import (
    FeatureUpdate,
    PullRequest,
    ReleaseInfoManifest,
)
from deploy.generate_release_notes.release_notes_writer import ReleaseNotesWriter


class TestReleaseNotesWriterUnit:
    """Unit tests for ReleaseNotesWriter with mocked Gemini API calls."""

    @patch("google.genai.Client")
    def test_render_with_mock_gemini(self, mock_client_cls):
        """Test ReleaseNotesWriter rendering with mocked Gemini Pro response."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_markdown_output = """# Data Commons Platform Release v1.1.1 (2026-07-29)

This release introduces Dataflow worker auto-scaling and Google Maps JavaScript API enablement for interactive map rendering.

---

## Key Feature Updates

### Dataflow Worker Auto-Scaling & Pipeline Safety
**What's New**: Platform operators can now configure Dataflow worker auto-scaling via Terraform variables.
**Why it Matters**: Improves ingestion throughput while preventing status race conditions.
**Capabilities & Changes**:
- Added `max_workers` Terraform variable ([`datacommons#189`](https://github.com/datacommonsorg/datacommons/pull/189))
- Removed premature success status setting at end of dataflow stage ([`datacommons#188`](https://github.com/datacommonsorg/datacommons/pull/188))

---

## Improvements & Configuration Updates

- **Google Maps API Enablement**: Enabled Google Maps JavaScript and Places APIs by default in Terraform ([`datacommons#198`](https://github.com/datacommonsorg/datacommons/pull/198))

---

## Bug Fixes

- **[Services]**: Resolved null pointer exception when querying empty StatVar observations ([`website#145`](https://github.com/datacommonsorg/website/pull/145))
"""
        mock_res = MagicMock()
        mock_res.text = mock_markdown_output
        mock_client.models.generate_content.return_value = mock_res

        pr188 = PullRequest(
            number=188,
            title="[DCP Ingestion] Remove status set to Success at end of dataflow stage",
            body="Fixes status race condition",
            author="gmechali",
            url="https://github.com/datacommonsorg/datacommons/pull/188",
            merged_at="2026-07-24T18:05:13Z",
            repo_name="datacommonsorg/datacommons",
        )
        pr189 = PullRequest(
            number=189,
            title="[DCP Ingestion] Allow dataflow to scale workers based on Terraform Variables",
            body="Adds max_workers variable",
            author="gmechali",
            url="https://github.com/datacommonsorg/datacommons/pull/189",
            merged_at="2026-07-24T19:13:17Z",
            repo_name="datacommonsorg/datacommons",
        )

        manifest = ReleaseInfoManifest(
            previous_version="v1.1.0",
            new_version="v1.1.1",
            all_pull_requests=[pr188, pr189],
        )

        feature = FeatureUpdate(
            id="ingestion_dataflow_scaling",
            title="Dataflow Worker Auto-Scaling & Pipeline Safety",
            description="Configured Dataflow worker auto-scaling via Terraform variables.",
            category="Ingestion & Safety",
            target_components=["dcp", "dataflow_worker"],
            included_prs=["datacommons#188", "datacommons#189"],
            pr_contributions={
                "datacommons#188": "Removed premature success status set at end of dataflow stage",
                "datacommons#189": "Added max_workers Terraform variable for Dataflow auto-scaling",
            },
            is_dcp_relevant=True,
        )

        writer = ReleaseNotesWriter(api_key="mock_key")
        output_md = writer.render(manifest=manifest, features=[feature], release_date="2026-07-29")

        assert "# Data Commons Platform Release v1.1.1 (2026-07-29)" in output_md
        assert "## Key Feature Updates" in output_md
        assert "## Improvements & Configuration Updates" in output_md
        assert "## Bug Fixes" in output_md
        assert "Dataflow Worker Auto-Scaling & Pipeline Safety" in output_md
        assert "[`datacommons#189`](https://github.com/datacommonsorg/datacommons/pull/189)" in output_md

    def test_build_audit_table_markdown(self):
        """Test generating optional Markdown audit table."""
        pr188 = PullRequest(
            number=188,
            title="Remove status set to Success | Dataflow Fix",
            body="",
            author="gmechali",
            url="https://github.com/datacommonsorg/datacommons/pull/188",
            merged_at="2026-07-24T18:05:13Z",
            repo_name="datacommonsorg/datacommons",
            target_components=["dcp"],
        )
        pr195 = PullRequest(
            number=195,
            title="chore: bump version to 1.1.1",
            body="",
            author="datacommons-robot-author",
            url="https://github.com/datacommonsorg/datacommons/pull/195",
            merged_at="2026-07-29T00:37:18Z",
            repo_name="datacommonsorg/datacommons",
            target_components=["dcp"],
        )

        manifest = ReleaseInfoManifest(
            previous_version="v1.1.0",
            new_version="v1.1.1",
            all_pull_requests=[pr188, pr195],
        )

        feature = FeatureUpdate(
            id="ingestion_fix",
            title="Dataflow Fix",
            description="Fixed dataflow status race condition.",
            category="Ingestion & Safety",
            included_prs=["datacommons#188"],
            is_dcp_relevant=True,
        )

        writer = ReleaseNotesWriter(api_key="mock_key", include_audit_log=True)
        table_md = writer.build_audit_table_markdown(manifest=manifest, features=[feature])

        assert "## Complete Release Audit Log" in table_md
        assert "| `datacommons` | [188](https://github.com/datacommonsorg/datacommons/pull/188) | Remove status set to Success \\| Dataflow Fix | @gmechali | dcp | Ingestion & Safety | Substantive Feature |" in table_md
        assert "Bot Version Bump" in table_md


class TestReleaseNotesWriterIntegration:
    """Integration test running ReleaseNotesWriter against real manifest and features from Steps 1 & 2."""

    @pytest.mark.integration
    def test_real_release_notes_generation_v1_1_0_to_v1_1_1(self):
        """Runs Gemini Pro Release Notes Writer against real /tmp/test_manifest_v1.1.1.json and /tmp/test_features_v1.1.1.json."""
        if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
            pytest.skip("GEMINI_API_KEY or GOOGLE_API_KEY not set in environment. Skipping real Gemini API integration test.")

        manifest_file = "/tmp/test_manifest_v1.1.1.json"
        features_file = "/tmp/test_features_v1.1.1.json"

        if not os.path.exists(manifest_file) or not os.path.exists(features_file):
            pytest.skip("Manifest or Features JSON file missing. Run Steps 1 and 2 tests first.")

        with open(manifest_file, "r") as f:
            manifest_dict = json.load(f)

        with open(features_file, "r") as f:
            features_dict = json.load(f)

        prs = [
            PullRequest(
                number=item["number"],
                title=item["title"],
                body="",
                author=item.get("author", "unknown"),
                url=f"https://github.com/{item['repo']}/pull/{item['number']}",
                merged_at="2026-07-25T00:00:00Z",
                repo_name=item["repo"],
                target_components=item.get("target_components", []),
            )
            for item in manifest_dict.get("sample_prs", [])
        ]

        manifest = ReleaseInfoManifest(
            previous_version=manifest_dict["previous_version"],
            new_version=manifest_dict["new_version"],
            all_pull_requests=prs,
        )

        features = [
            FeatureUpdate(
                id=item["id"],
                title=item["title"],
                description=item["description"],
                category=item["category"],
                target_components=item.get("target_components", []),
                included_prs=item.get("included_prs", []),
                pr_contributions=item.get("pr_contributions", {}),
                is_dcp_relevant=item.get("is_dcp_relevant", True),
            )
            for item in features_dict
        ]

        writer = ReleaseNotesWriter()
        markdown_output = writer.render(
            manifest=manifest,
            features=features,
            additional_instructions="Highlight Google Maps API enablement and Dataflow worker scaling.",
            release_date="2026-07-29",
        )

        assert len(markdown_output) > 100
        print(f"\nSuccessfully generated release notes ({len(markdown_output)} chars):")
        print("=" * 60)
        print(markdown_output[:500] + "\n...\n")
        print("=" * 60)

        # Save to /tmp/RELEASE_NOTES_v1.1.1.md
        output_file = "/tmp/RELEASE_NOTES_v1.1.1.md"
        with open(output_file, "w") as f:
            f.write(markdown_output)

        print(f"Saved complete release notes to {output_file}")
        assert os.path.exists(output_file)
