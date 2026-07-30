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

"""Unit and Integration tests for Feature Extractor (deploy/generate_release_notes/feature_extractor.py)."""

import json
import os
from unittest.mock import MagicMock, patch
import pytest

from deploy.generate_release_notes.feature_extractor import FeatureExtractor
from deploy.generate_release_notes.models import (
    FeatureUpdate,
    PullRequest,
    ReleaseInfoManifest,
)


class TestFeatureExtractorUnit:
    """Unit tests for FeatureExtractor with mocked Gemini API calls."""

    @patch("google.genai.Client")
    def test_filter_prs_with_flash(self, mock_client_cls):
        """Test Stage 1 Flash model filtering out bot version bumps and noise."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # Mock Flash model response returning PRs datacommons#188 and datacommons#189
        mock_res = MagicMock()
        mock_res.text = json.dumps({"relevant_pr_ids": ["datacommons#188", "datacommons#189"]})
        mock_client.models.generate_content.return_value = mock_res

        pr188 = PullRequest(
            number=188,
            title="[DCP Ingestion] Remove status set to Success at end of dataflow stage",
            body="Fixes status race condition",
            author="gmechali",
            url="https://github.com/datacommonsorg/datacommons/pull/188",
            merged_at="2026-07-24T18:05:13Z",
            repo_name="datacommonsorg/datacommons",
            files_changed=["infra/dcp/dataflow_job.tf"],
        )
        pr189 = PullRequest(
            number=189,
            title="[DCP Ingestion] Allow dataflow to scale workers based on Terraform Variables",
            body="Adds max_workers variable",
            author="gmechali",
            url="https://github.com/datacommonsorg/datacommons/pull/189",
            merged_at="2026-07-24T19:13:17Z",
            repo_name="datacommonsorg/datacommons",
            files_changed=["infra/dcp/variables.tf"],
        )
        pr195_bot = PullRequest(
            number=195,
            title="chore: bump version to 1.1.1",
            body="Automated release bump",
            author="datacommons-robot-author",
            url="https://github.com/datacommonsorg/datacommons/pull/195",
            merged_at="2026-07-29T00:37:18Z",
            repo_name="datacommonsorg/datacommons",
            files_changed=["VERSION"],
        )

        manifest = ReleaseInfoManifest(
            previous_version="v1.1.0",
            new_version="v1.1.1",
            all_pull_requests=[pr188, pr189, pr195_bot],
        )

        extractor = FeatureExtractor(api_key="mock_key")
        candidates = extractor.filter_prs_with_flash(manifest)

        assert len(candidates) == 2
        candidate_ids = [pr.qualified_id for pr in candidates]
        assert "datacommons#188" in candidate_ids
        assert "datacommons#189" in candidate_ids
        assert "datacommons#195" not in candidate_ids

    @patch("google.genai.Client")
    def test_synthesize_features_with_pro(self, mock_client_cls):
        """Test Stage 2 Pro model feature grouping and SOP classification."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_synthesis_output = [
            {
                "id": "ingestion_dataflow_scaling",
                "title": "Dataflow Worker Auto-Scaling & Pipeline Safety",
                "description": "Configured Dataflow worker auto-scaling via Terraform variables and resolved premature success status marking.",
                "category": "Ingestion & Safety",
                "target_components": ["dcp", "dataflow_worker"],
                "included_prs": ["datacommons#188", "datacommons#189"],
                "is_dcp_relevant": True,
                "breaking_changes": None,
            }
        ]
        mock_res = MagicMock()
        mock_res.text = json.dumps(mock_synthesis_output)
        mock_client.models.generate_content.return_value = mock_res

        pr188 = PullRequest(
            number=188,
            title="[DCP Ingestion] Remove status set to Success at end of dataflow stage",
            body="Fixes status race condition",
            author="gmechali",
            url="https://github.com/datacommonsorg/datacommons/pull/188",
            merged_at="2026-07-24T18:05:13Z",
            repo_name="datacommonsorg/datacommons",
            files_changed=["infra/dcp/dataflow_job.tf"],
        )
        pr189 = PullRequest(
            number=189,
            title="[DCP Ingestion] Allow dataflow to scale workers based on Terraform Variables",
            body="Adds max_workers variable",
            author="gmechali",
            url="https://github.com/datacommonsorg/datacommons/pull/189",
            merged_at="2026-07-24T19:13:17Z",
            repo_name="datacommonsorg/datacommons",
            files_changed=["infra/dcp/variables.tf"],
        )

        manifest = ReleaseInfoManifest(
            previous_version="v1.1.0",
            new_version="v1.1.1",
            all_pull_requests=[pr188, pr189],
        )

        extractor = FeatureExtractor(api_key="mock_key")
        features = extractor.synthesize_features_with_pro(
            manifest=manifest,
            candidate_prs=[pr188, pr189],
            additional_instructions="Focus on Dataflow scaling",
        )

        assert len(features) == 1
        feature = features[0]
        assert isinstance(feature, FeatureUpdate)
        assert feature.id == "ingestion_dataflow_scaling"
        assert feature.category == "Ingestion & Safety"
        assert feature.included_prs == ["datacommons#188", "datacommons#189"]
        assert feature.is_dcp_relevant is True


class TestFeatureExtractorIntegration:
    """Integration test running FeatureExtractor against real manifest from Step 1 with Gemini API."""

    @pytest.mark.integration
    def test_real_feature_extraction_v1_1_0_to_v1_1_1(self):
        """Runs 2-stage Gemini pipeline against real /tmp/test_manifest_v1.1.1.json."""
        if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
            pytest.skip("GEMINI_API_KEY or GOOGLE_API_KEY not set in environment. Skipping real Gemini API integration test.")

        manifest_file = "/tmp/test_manifest_v1.1.1.json"
        if not os.path.exists(manifest_file):
            pytest.skip(f"Manifest file {manifest_file} not found. Run Step 1 test first.")

        # Re-construct ReleaseInfoManifest from test manifest summary
        with open(manifest_file, "r") as f:
            manifest_dict = json.load(f)

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

        extractor = FeatureExtractor()
        features = extractor.extract_features(
            manifest=manifest,
            additional_instructions="Integrate Maps API and Dataflow scaling highlights.",
        )

        assert len(features) > 0
        print(f"\nSuccessfully extracted {len(features)} feature updates using Gemini pipeline:")
        for feat in features:
            print(f"  - [{feat.category}] {feat.title} (PRs: {feat.included_prs})")

        # Save features to /tmp for inspection
        output_file = "/tmp/test_features_v1.1.1.json"
        features_dict = [
            {
                "id": f.id,
                "title": f.title,
                "description": f.description,
                "category": f.category,
                "target_components": f.target_components,
                "included_prs": f.included_prs,
                "is_dcp_relevant": f.is_dcp_relevant,
            }
            for f in features
        ]
        with open(output_file, "w") as f:
            json.dump(features_dict, f, indent=2)

        print(f"Saved synthesized features summary to {output_file}")
        assert os.path.exists(output_file)
