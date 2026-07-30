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

"""CLI Entry Point for Data Commons Platform (DCP) Release Notes Generator.

Orchestrates Step 1 (PR Extractor), Step 2 (Feature Extractor), and Step 3 (Release Notes Writer).

Usage:
  uv run --group generate-release-notes python -m deploy.generate_release_notes \\
    --prev v1.1.0 --new v1.1.1 \\
    [--out ./RELEASE_NOTES_v1.1.1.md] \\
    [--additional-instructions ./context.md] \\
    [--allow-missing-images] \\
    [--include-audit-log]
"""

import json
import logging
import os
import sys
from typing import Optional

import click

from deploy.generate_release_notes.feature_extractor import (
    DEFAULT_MODEL as DEFAULT_FEATURE_MODEL,
    FeatureExtractor,
)
from deploy.generate_release_notes.pr_extractor import PRExtractor
from deploy.generate_release_notes.release_notes_writer import (
    DEFAULT_WRITER_MODEL,
    ReleaseNotesWriter,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("generate_release_notes")


@click.command(
    help="Generate publication-ready Data Commons Platform (DCP) release notes between two release versions."
)
@click.option(
    "--prev",
    "prev_version",
    required=True,
    help="Previous release tag (e.g. v1.1.0 or 1.1.0).",
)
@click.option(
    "--new",
    "new_version",
    required=True,
    help="New release tag (e.g. v1.1.1 or 1.1.1).",
)
@click.option(
    "--out",
    "output_path",
    default=None,
    help="Output file path for generated Markdown release notes (default: ./RELEASE_NOTES_<new_version>.md).",
)
@click.option(
    "--additional-instructions",
    "additional_instructions",
    default=None,
    help="Path to markdown file or raw text containing additional context, highlights, or custom notes.",
)
@click.option(
    "--allow-missing-images",
    is_flag=True,
    default=False,
    help="Bypass missing container image tag errors during staging/testing.",
)
@click.option(
    "--include-audit-log",
    is_flag=True,
    default=False,
    help="Append complete raw PR audit log table at the bottom of the release notes.",
)
@click.option(
    "--synthesis-model",
    "--filter-model",
    "synthesis_model",
    default=DEFAULT_FEATURE_MODEL,
    help=f"Gemini model for Step 2 feature synthesis (default: {DEFAULT_FEATURE_MODEL}).",
)
@click.option(
    "--writer-model",
    default=DEFAULT_WRITER_MODEL,
    help=f"Gemini model for Step 3 release notes writing (default: {DEFAULT_WRITER_MODEL}).",
)
@click.option(
    "--manifest-out",
    default=None,
    help="Optional path to save raw Step 1 ReleaseInfoManifest JSON.",
)
@click.option(
    "--features-out",
    default=None,
    help="Optional path to save synthesized Step 2 FeatureUpdate JSON.",
)
def main(
    prev_version: str,
    new_version: str,
    output_path: Optional[str],
    additional_instructions: Optional[str],
    allow_missing_images: bool,
    include_audit_log: bool,
    synthesis_model: str,
    writer_model: str,
    manifest_out: Optional[str],
    features_out: Optional[str],
):
    """Executes the 3-step DCP Release Notes Generation Pipeline."""
    # Normalize versions
    if not prev_version.startswith("v"):
        prev_version = f"v{prev_version}"
    if not new_version.startswith("v"):
        new_version = f"v{new_version}"

    if not output_path:
        output_path = f"./RELEASE_NOTES_{new_version}.md"

    # Read additional instructions file if path provided
    instructions_text = None
    if additional_instructions:
        if os.path.exists(additional_instructions):
            with open(additional_instructions, "r") as f:
                instructions_text = f.read().strip()
            logger.info(f"Loaded additional instructions from {additional_instructions}")
        else:
            instructions_text = additional_instructions
            logger.info("Using inline additional instructions.")

    logger.info("=" * 60)
    logger.info(f" Starting DCP Release Notes Generation: {prev_version} -> {new_version}")
    logger.info("=" * 60)

    # ----------------------------------------------------
    # STEP 1: Sourcing PRs & Component Version Info
    # ----------------------------------------------------
    logger.info("\n--- STEP 1: Sourcing PRs & Resolving Image Tags ---")
    pr_extractor = PRExtractor(skip_missing_images=allow_missing_images)
    try:
        manifest = pr_extractor.extract(
            prev_version=prev_version,
            new_version=new_version,
            additional_instructions=instructions_text,
        )
    except Exception as e:
        logger.error(f"Step 1 Sourcing Failed: {e}")
        sys.exit(1)

    if manifest_out:
        manifest_dict = {
            "previous_version": manifest.previous_version,
            "new_version": manifest.new_version,
            "total_prs": len(manifest.all_pull_requests),
            "components": {
                k: {
                    "name": v.component_name,
                    "repo": v.repo_name,
                    "prev_sha": v.previous_sha,
                    "new_sha": v.new_sha,
                    "image_uri": v.image_uri,
                    "pull_requests_count": len(manifest.pull_requests_by_component.get(k, [])),
                    "pull_requests": [
                        {
                            "id": pr.qualified_id,
                            "title": pr.title,
                            "author": pr.author,
                            "repo": pr.repo_name,
                            "url": pr.url,
                            "merged_at": pr.merged_at,
                            "files_changed": pr.files_changed,
                        }
                        for pr in manifest.pull_requests_by_component.get(k, [])
                    ],
                }
                for k, v in manifest.components.items()
            },
        }
        with open(manifest_out, "w") as f:
            json.dump(manifest_dict, f, indent=2)
        logger.info(f"Saved manifest with PRs per image to {manifest_out}")

    # ----------------------------------------------------
    # STEP 2: Feature Extraction & SOP Classification
    # ----------------------------------------------------
    logger.info("\n--- STEP 2: Feature Extraction & SOP Classification ---")
    feature_extractor = FeatureExtractor(
        model_name=synthesis_model,
    )
    try:
        features = feature_extractor.extract_features(
            manifest=manifest,
            additional_instructions=instructions_text,
        )
    except Exception as e:
        logger.error(f"Step 2 Feature Extraction Failed: {e}")
        sys.exit(1)

    if features_out:
        features_dict = [
            {
                "id": f.id,
                "title": f.title,
                "description": f.description,
                "category": f.category,
                "included_prs": f.included_prs,
                "pr_contributions": f.pr_contributions,
                "is_dcp_relevant": f.is_dcp_relevant,
            }
            for f in features
        ]
        with open(features_out, "w") as f:
            json.dump(features_dict, f, indent=2)
        logger.info(f"Saved synthesized features to {features_out}")

    # ----------------------------------------------------
    # STEP 3: Release Notes Writing
    # ----------------------------------------------------
    logger.info("\n--- STEP 3: Release Notes Writing ---")
    writer = ReleaseNotesWriter(
        model_name=writer_model,
        include_audit_log=include_audit_log,
    )
    try:
        markdown_notes = writer.render(
            manifest=manifest,
            features=features,
            additional_instructions=instructions_text,
        )
    except Exception as e:
        logger.error(f"Step 3 Release Notes Writing Failed: {e}")
        sys.exit(1)

    # Save output to disk
    with open(output_path, "w") as f:
        f.write(markdown_notes)

    logger.info("=" * 60)
    logger.info(f"🎉 Success! Publication-ready release notes written to: {output_path}")
    logger.info(f"   - Total PRs Processed: {len(manifest.all_pull_requests)}")
    logger.info(f"   - Synthesized Feature Updates: {len(features)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
