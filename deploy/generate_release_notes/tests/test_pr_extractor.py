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

"""Unit and Integration tests for PR Extractor (deploy/generate_release_notes/pr_extractor.py)."""

import json
import os
from unittest.mock import MagicMock, patch
import pytest

from deploy.generate_release_notes.config import COMPONENTS, SourceRule
from deploy.generate_release_notes.models import PullRequest, ReleaseInfoManifest
from deploy.generate_release_notes.pr_extractor import PRExtractor


class TestPRExtractorUnit:
    """Unit tests for PRExtractor helper functions and SourceRule matching."""

    def test_source_rule_path_filtering(self):
        """Test multi-source path filtering rules across website and import repos."""
        extractor = PRExtractor()

        # 1. Website PR modifying build/cdc_data/ -> Preprocessor
        pr_cdc_data = PullRequest(
            number=101,
            title="Update cdc_data Dockerfile",
            body="",
            author="testuser",
            url="https://github.com/datacommonsorg/website/pull/101",
            merged_at="2026-07-20T10:00:00Z",
            repo_name="datacommonsorg/website",
            files_changed=["build/cdc_data/Dockerfile", "build/cdc_data/run.sh"],
        )

        # 2. Website PR modifying server/ -> Services
        pr_website_server = PullRequest(
            number=102,
            title="Update Flask routes",
            body="",
            author="testuser",
            url="https://github.com/datacommonsorg/website/pull/102",
            merged_at="2026-07-21T10:00:00Z",
            repo_name="datacommonsorg/website",
            files_changed=["server/routes.py", "static/js/app.js"],
        )

        # 3. Import PR modifying simple/ -> Preprocessor
        pr_import_simple = PullRequest(
            number=201,
            title="Update CSV parser in simple importer",
            body="",
            author="testuser",
            url="https://github.com/datacommonsorg/import/pull/201",
            merged_at="2026-07-22T10:00:00Z",
            repo_name="datacommonsorg/import",
            files_changed=["simple/parser.py", "simple/main.go"],
        )

        # 4. Import PR modifying pipeline/workflow/ingestion-helper/ -> Ingestion Helper
        pr_import_ingestion = PullRequest(
            number=202,
            title="Fix ingestion helper Spanner query",
            body="",
            author="testuser",
            url="https://github.com/datacommonsorg/import/pull/202",
            merged_at="2026-07-23T10:00:00Z",
            repo_name="datacommonsorg/import",
            files_changed=["pipeline/workflow/ingestion-helper/main.go"],
        )

        # Rules
        rule_prep_website = SourceRule(repo="datacommonsorg/website", path_filter="build/cdc_data/")
        rule_services_website = SourceRule(repo="datacommonsorg/website", path_filter=None)
        rule_prep_import = SourceRule(repo="datacommonsorg/import", path_filter="simple/")
        rule_ingestion_helper = SourceRule(repo="datacommonsorg/import", path_filter="pipeline/workflow/ingestion-helper/")

        # Assertions
        assert extractor.is_pr_matching_rule(pr_cdc_data, rule_prep_website) is True
        assert extractor.is_pr_matching_rule(pr_website_server, rule_prep_website) is False
        assert extractor.is_pr_matching_rule(pr_website_server, rule_services_website) is True

        assert extractor.is_pr_matching_rule(pr_import_simple, rule_prep_import) is True
        assert extractor.is_pr_matching_rule(pr_import_ingestion, rule_prep_import) is False
        assert extractor.is_pr_matching_rule(pr_import_ingestion, rule_ingestion_helper) is True

    @patch("deploy.generate_release_notes.pr_extractor.subprocess.run")
    def test_gcloud_image_tag_resolution(self, mock_run):
        """Test resolving container image tags via gcloud list-tags mock."""
        mock_output = [
            {
                "digest": "sha256:1234567890abcdef",
                "tags": ["1.1.1", "latest"],
                "timestamp": {"datetime": "2026-07-15 12:00:00-07:00"},
            }
        ]
        mock_res = MagicMock()
        mock_res.stdout = json.dumps(mock_output)
        mock_run.return_value = mock_res

        extractor = PRExtractor()
        info = extractor.resolve_image_tag_info("gcr.io/datcom-ci/datacommons-services", "1.1.1")

        assert info is not None
        assert info["digest"] == "sha256:1234567890abcdef"
        assert info["timestamp"]["datetime"] == "2026-07-15 12:00:00-07:00"


class TestPRExtractorIntegration:
    """Integration test executing PRExtractor against real GitHub repositories."""

    @pytest.mark.integration
    def test_real_pr_extraction_v1_1_0_to_v1_1_1(self):
        """Extracts PRs between v1.1.0 and v1.1.1 across public Data Commons repos."""
        extractor = PRExtractor()
        manifest = extractor.extract(
            prev_version="v1.1.0",
            new_version="v1.1.1",
            additional_instructions="Integration test run for v1.1.0 -> v1.1.1",
        )

        assert isinstance(manifest, ReleaseInfoManifest)
        assert manifest.previous_version == "v1.1.0"
        assert manifest.new_version == "v1.1.1"
        assert len(manifest.components) > 0

        # Dump manifest to /tmp for schema inspection
        output_file = "/tmp/test_manifest_v1.1.1.json"
        manifest_dict = {
            "previous_version": manifest.previous_version,
            "new_version": manifest.new_version,
            "total_prs_extracted": len(manifest.all_pull_requests),
            "components": {
                k: {
                    "id": v.component_id,
                    "name": v.component_name,
                    "prev_timestamp": v.prev_timestamp,
                    "new_timestamp": v.new_timestamp,
                }
                for k, v in manifest.components.items()
            },
            "pull_requests_count_by_component": {
                k: len(v) for k, v in manifest.pull_requests_by_component.items()
            },
            "sample_prs": [
                {
                    "number": pr.number,
                    "title": pr.title,
                    "author": pr.author,
                    "repo": pr.repo_name,
                    "target_components": pr.target_components,
                }
                for pr in manifest.all_pull_requests[:10]
            ],
        }

        with open(output_file, "w") as f:
            json.dump(manifest_dict, f, indent=2)

        print(f"\nSaved integration test manifest summary to {output_file}")
        assert os.path.exists(output_file)
