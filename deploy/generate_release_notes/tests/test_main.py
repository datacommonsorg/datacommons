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

"""Unit tests for CLI Entry Point (deploy/generate_release_notes/main.py)."""

from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from deploy.generate_release_notes.main import main
from deploy.generate_release_notes.models import (
    FeatureUpdate,
    PullRequest,
    ReleaseInfoManifest,
)


class TestMainCLI:
    """Tests for main CLI entry point."""

    @patch("deploy.generate_release_notes.main.PRExtractor")
    @patch("deploy.generate_release_notes.main.FeatureExtractor")
    @patch("deploy.generate_release_notes.main.ReleaseNotesWriter")
    def test_main_cli_success(
        self, mock_writer_cls, mock_feature_cls, mock_pr_cls, tmp_path
    ):
        """Test end-to-end CLI execution with mocked Step 1, Step 2, and Step 3."""
        # 1. Mock PRExtractor
        mock_pr_instance = MagicMock()
        mock_pr_cls.return_value = mock_pr_instance
        manifest = ReleaseInfoManifest(
            previous_version="v1.1.0",
            new_version="v1.1.1",
            all_pull_requests=[
                PullRequest(
                    number=188,
                    title="Remove status set to Success",
                    body="",
                    author="gmechali",
                    url="https://github.com/datacommonsorg/datacommons/pull/188",
                    merged_at="2026-07-24T18:05:13Z",
                    repo_name="datacommonsorg/datacommons",
                )
            ],
        )
        mock_pr_instance.extract.return_value = manifest

        # 2. Mock FeatureExtractor
        mock_feature_instance = MagicMock()
        mock_feature_cls.return_value = mock_feature_instance
        feature = FeatureUpdate(
            id="dataflow_fix",
            title="Dataflow Fix",
            description="Fixed dataflow status set.",
            category="Ingestion & Safety",
            included_prs=["datacommons#188"],
            is_dcp_relevant=True,
        )
        mock_feature_instance.extract_features.return_value = [feature]

        # 3. Mock ReleaseNotesWriter
        mock_writer_instance = MagicMock()
        mock_writer_cls.return_value = mock_writer_instance
        mock_writer_instance.render.return_value = "# Data Commons Platform Release v1.1.1 (2026-07-29)\n\nSample release notes."

        out_file = tmp_path / "RELEASE_NOTES_v1.1.1.md"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--prev",
                "1.1.0",
                "--new",
                "1.1.1",
                "--out",
                str(out_file),
                "--allow-missing-images",
            ],
        )

        assert result.exit_code == 0
        assert out_file.exists()
        assert out_file.read_text() == "# Data Commons Platform Release v1.1.1 (2026-07-29)\n\nSample release notes."
