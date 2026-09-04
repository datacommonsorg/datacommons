#!/usr/bin/env python3
# Copyright 2026 Google LLC.
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

"""tag_release_artifacts.py - Multi-Artifact Release Tagging & Template Staging.

PURPOSE:
  Automates the cross-tagging of container images and the staging/re-rendering
  of the Dataflow Flex Template JSON spec across GCR, Artifact Registry, and GCS.

ARTIFACTS MANAGED:
  1. Services Image:            gcr.io/datcom-ci/datacommons-services
  2. Preprocessor Image:        gcr.io/datcom-ci/datacommons-data
  3. Postprocessor Image:       gcr.io/datcom-ci/datacommons-aggregation-helper
  4. Ingestion Helper Image:    gcr.io/datcom-ci/datacommons-ingestion-helper
  5. Dataflow Worker Image:     us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion
  6. Dataflow Flex Template:    gs://datcom-templates/templates/flex/ingestion-<TAG>.json

NOTE ON INTENTIONAL SELF-CONTAINMENT:
  This script is intentionally self-contained using only the Python standard library
  so that it can run reliably inside minimal Cloud Build builders (e.g. google/cloud-sdk:slim)
  without PYTHONPATH configuration or external PyPI dependencies.

USAGE EXAMPLES:
  # 1. Staging candidate with a default baseline and a services commit override:
  python3 deploy/scripts/tag_release_artifacts.py \\
    --target-tag "1.1.2rc1" \\
    --default-source-tag "1.1.1" \\
    --services-tag "1574ed3-79627f8-e265a1d"

  # 2. Promoting a verified release candidate to production:
  python3 deploy/scripts/tag_release_artifacts.py \\
    --target-tag "1.1.2" \\
    --default-source-tag "1.1.2rc1"

  # 3. Dry-run inspection:
  python3 deploy/scripts/tag_release_artifacts.py \\
    --target-tag "1.1.2rc1" \\
    --default-source-tag "1.1.1" \\
    --dry-run
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 1. Standard Cloud Run Container Images
CONTAINER_IMAGE_MAP = {
    "services": "gcr.io/datcom-ci/datacommons-services",
    "preprocessor": "gcr.io/datcom-ci/datacommons-data",
    "postprocessor": "gcr.io/datcom-ci/datacommons-aggregation-helper",
    "ingestion_helper": "gcr.io/datcom-ci/datacommons-ingestion-helper",
}

# 2. Dataflow Flex Template & Worker Image Artifacts
DATAFLOW_CONFIG = {
    "image_repo": "us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion",
    "template_gcs_base": "gs://datcom-templates/templates/flex",
}

DATAFLOW_IMAGE_REPO = DATAFLOW_CONFIG["image_repo"]
DEFAULT_TEMPLATE_GCS_BASE = DATAFLOW_CONFIG["template_gcs_base"]

# Anchored SemVer / PEP 440 regex matching releases (1.2.3), pre-releases (1.2.3rc1),
# and development versions (1.2.0.dev0).
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?(?:\.dev\d+)?$")


def normalize_tag(tag: str) -> str:
    """Strips whitespace and leading 'v' prefix from version tags."""
    return tag.strip().lstrip("v").strip()


def tag_container_image(
    repo: str,
    src_tag: str,
    target_tag: str,
    *,
    dry_run: bool = False,
) -> None:
    """Adds a new tag to an existing container image in GCR/Artifact Registry."""
    src_image = src_tag if "/" in src_tag else f"{repo}:{src_tag}"
    target_image = f"{repo}:{target_tag}"

    if "pkg.dev" in repo or "pkg.dev" in src_image:
        cmd = [
            "gcloud",
            "artifacts",
            "docker",
            "tags",
            "add",
            src_image,
            target_image,
            "--quiet",
        ]
    else:
        cmd = [
            "gcloud",
            "container",
            "images",
            "add-tag",
            src_image,
            target_image,
            "--quiet",
        ]

    print(f"  [IMAGE] Tagging {src_image} -> {target_image}")
    if dry_run:
        print(f"          [DRY-RUN] Executing: {' '.join(cmd)}")
        return

    try:
        res = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        if res.stdout.strip():
            print(f"          {res.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        sys.exit(
            f"Error: Failed to tag image '{src_image}' -> '{target_image}'.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Details: {e.stderr.strip() or e.stdout.strip()}"
        )


def stage_dataflow_artifacts(
    gcs_base: str,
    template_tag: str,
    target_tag: str,
    dataflow_image_repo: str = DATAFLOW_IMAGE_REPO,
    image_tag: str | None = None,
    *,
    dry_run: bool = False,
) -> None:
    """Downloads source template spec, resolves source image, tags worker image, and uploads target template."""
    src_uri = f"{gcs_base.rstrip('/')}/ingestion-{template_tag}.json"
    target_uri = f"{gcs_base.rstrip('/')}/ingestion-{target_tag}.json"
    target_image = f"{dataflow_image_repo}:{target_tag}"

    src_image = (
        (
            image_tag
            if ("/" in image_tag or ":" in image_tag)
            else f"{dataflow_image_repo}:{image_tag}"
        )
        if image_tag
        else None
    )

    print("  [DATAFLOW] Staging Dataflow Flex Template & Tagging Worker Image:")
    print(f"             Source Template: {src_uri}")
    print(f"             Target Template: {target_uri}")
    print(f"             Target Image:    {target_image}")

    if dry_run:
        if src_image:
            print(f"             Source Image:    {src_image} (explicit override)")
        else:
            print(
                f"             Source Image:    [dynamic from template {src_uri}['image']]"
            )
        print(
            f"             [DRY-RUN] Would download {src_uri}, tag image -> {target_image}, set image={target_image}, and upload to {target_uri}"
        )
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        local_src = tmp_path / f"ingestion-{template_tag}.json"
        local_target = tmp_path / f"ingestion-{target_tag}.json"

        # 1. Download source template spec
        cp_in_cmd = ["gcloud", "storage", "cp", src_uri, str(local_src)]
        try:
            subprocess.run(
                cp_in_cmd,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            sys.exit(
                f"Error: Failed to download source Dataflow template '{src_uri}'.\n"
                f"Command: {' '.join(cp_in_cmd)}\n"
                f"Details: {e.stderr.strip() or e.stdout.strip()}"
            )

        # 2. Parse and validate JSON template structure
        try:
            data = json.loads(local_src.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Template JSON root must be a dictionary object.")
        except (json.JSONDecodeError, OSError, ValueError) as e:
            sys.exit(
                f"Error: Failed to parse JSON in downloaded template '{src_uri}': {e}"
            )

        # 3. Resolve source container image
        if not src_image:
            src_image = data.get("image")
            if not src_image or not isinstance(src_image, str):
                sys.exit(
                    f"Error: Source template '{src_uri}' missing valid 'image' property (got: {src_image})."
                )

        print(f"             Source Image:    {src_image}")

        # 4. Tag the source image to target tag in Artifact Registry
        tag_container_image(
            repo=dataflow_image_repo,
            src_tag=src_image,
            target_tag=target_tag,
            dry_run=dry_run,
        )

        # 5. Update JSON template and upload to target URI
        data["image"] = target_image
        local_target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        cp_out_cmd = ["gcloud", "storage", "cp", str(local_target), target_uri]
        try:
            subprocess.run(
                cp_out_cmd,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            sys.exit(
                f"Error: Failed to upload updated Dataflow template to '{target_uri}'.\n"
                f"Command: {' '.join(cp_out_cmd)}\n"
                f"Details: {e.stderr.strip() or e.stdout.strip()}"
            )


# Backward compatibility alias
stage_dataflow_template = stage_dataflow_artifacts


def tag_all_artifacts(
    target_tag: str,
    default_source_tag: str | None = None,
    services_tag: str | None = None,
    preprocessor_tag: str | None = None,
    postprocessor_tag: str | None = None,
    ingestion_helper_tag: str | None = None,
    dataflow_template_tag: str | None = None,
    dataflow_image_tag: str | None = None,
    template_gcs_base: str = DEFAULT_TEMPLATE_GCS_BASE,
    *,
    dry_run: bool = False,
) -> None:
    """Resolves tags for all artifacts and coordinates container tagging and template staging."""
    target_tag = normalize_tag(target_tag)
    if not target_tag:
        sys.exit("Error: Target tag cannot be empty.")
    if not VERSION_PATTERN.match(target_tag):
        sys.exit(
            f"Error: Invalid target tag format '{target_tag}'. "
            "Must follow SemVer / PEP 440 (e.g. '1.2.3' or '1.2.3rc1')."
        )

    # Validate gcloud availability when performing actual execution
    if not dry_run and not shutil.which("gcloud"):
        sys.exit(
            "Error: 'gcloud' command-line tool not found in PATH. "
            "Please ensure Google Cloud SDK is installed and in your PATH."
        )

    # Resolve source tags with fallback hierarchy
    default_src = normalize_tag(default_source_tag) if default_source_tag else None
    resolved_sources = {
        "services": normalize_tag(services_tag) if services_tag else default_src,
        "preprocessor": (
            normalize_tag(preprocessor_tag) if preprocessor_tag else default_src
        ),
        "postprocessor": (
            normalize_tag(postprocessor_tag) if postprocessor_tag else default_src
        ),
        "ingestion_helper": (
            normalize_tag(ingestion_helper_tag) if ingestion_helper_tag else default_src
        ),
    }

    # Dataflow Flex Template resolution
    resolved_template_tag = (
        normalize_tag(dataflow_template_tag) if dataflow_template_tag else default_src
    )
    # Redirect abandoned 'latest' alias to 'stable' for Dataflow template
    # (mirroring Terraform logic in infra/dcp/main.tf)
    if resolved_template_tag == "latest":
        resolved_template_tag = "stable"

    resolved_image_tag = (
        normalize_tag(dataflow_image_tag) if dataflow_image_tag else None
    )

    # Validate that every required artifact has a resolved source tag
    missing_sources = [k for k, v in resolved_sources.items() if not v]
    if not resolved_template_tag:
        missing_sources.append("dataflow_template")

    if missing_sources:
        sys.exit(
            f"Error: Missing source tag for artifact(s): {', '.join(missing_sources)}.\n"
            f"Please specify --default-source-tag or provide specific --<artifact>-tag flags."
        )

    print("=" * 72)
    print(f"RELEASE ARTIFACT TAGGING PLAN -> Target: '{target_tag}'")
    print("=" * 72)
    for artifact, repo in CONTAINER_IMAGE_MAP.items():
        src = resolved_sources[artifact]
        print(f"  * {artifact:<18}: {src} -> {target_tag} ({repo})")

    df_img_plan = (
        f"{resolved_image_tag} -> {target_tag}"
        if resolved_image_tag
        else f"[from template {resolved_template_tag}] -> {target_tag}"
    )
    print(f"  * {'dataflow_image':<18}: {df_img_plan} ({DATAFLOW_IMAGE_REPO})")
    print(
        f"  * {'flex_template':<18}: ingestion-{resolved_template_tag}.json -> ingestion-{target_tag}.json"
    )
    print("=" * 72)

    # 1. Tag standard container images
    print("\n1. Tagging Standard Container Images:")
    for artifact, repo in CONTAINER_IMAGE_MAP.items():
        src = resolved_sources[artifact]
        tag_container_image(
            repo=repo,
            src_tag=src,
            target_tag=target_tag,
            dry_run=dry_run,
        )

    # 2. Stage Dataflow Flex Template JSON & Tag Worker Image
    print("\n2. Staging Dataflow Flex Template & Tagging Worker Image:")
    stage_dataflow_artifacts(
        gcs_base=template_gcs_base,
        template_tag=resolved_template_tag,
        target_tag=target_tag,
        dataflow_image_repo=DATAFLOW_IMAGE_REPO,
        image_tag=resolved_image_tag,
        dry_run=dry_run,
    )

    if dry_run:
        print("\nDry-run complete. No artifacts were modified.")
    else:
        print("\nAll release artifacts tagged and staged successfully!")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tag and stage release container images and Dataflow Flex Templates."
    )
    parser.add_argument(
        "--target-tag",
        required=True,
        help="The target release version or candidate tag (e.g. 1.1.2 or 1.1.2rc1).",
    )
    parser.add_argument(
        "--default-source-tag",
        help="Default baseline source tag inherited by all artifacts unless explicitly overridden.",
    )
    parser.add_argument(
        "--services-tag",
        "--services-source-tag",
        dest="services_tag",
        help="Source tag or commit SHA for datacommons-services image.",
    )
    parser.add_argument(
        "--preprocessor-tag",
        "--preprocessor-source-tag",
        dest="preprocessor_tag",
        help="Source tag for datacommons-data (preprocessor) image.",
    )
    parser.add_argument(
        "--postprocessor-tag",
        "--postprocessor-source-tag",
        dest="postprocessor_tag",
        help="Source tag for datacommons-aggregation-helper (postprocessor) image.",
    )
    parser.add_argument(
        "--ingestion-helper-tag",
        "--ingestion-helper-source-tag",
        dest="ingestion_helper_tag",
        help="Source tag for datacommons-ingestion-helper image.",
    )
    parser.add_argument(
        "--dataflow-template-tag",
        "--dataflow-template-source-tag",
        dest="dataflow_template_tag",
        help="Source tag for Dataflow Flex Template spec in GCS (e.g. 'stable' or '1.1.2').",
    )
    parser.add_argument(
        "--dataflow-image-tag",
        "--dataflow-image-source-tag",
        dest="dataflow_image_tag",
        help=(
            "Optional explicit override for Dataflow worker image tag. "
            "If omitted, automatically resolved from the source Flex Template JSON."
        ),
    )
    parser.add_argument(
        "--template-bucket",
        default=DEFAULT_TEMPLATE_GCS_BASE,
        help=f"GCS bucket directory for Dataflow Flex Templates (default: {DEFAULT_TEMPLATE_GCS_BASE}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned operations without executing gcloud tagging or uploads.",
    )

    args = parser.parse_args()

    tag_all_artifacts(
        target_tag=args.target_tag,
        default_source_tag=args.default_source_tag,
        services_tag=args.services_tag,
        preprocessor_tag=args.preprocessor_tag,
        postprocessor_tag=args.postprocessor_tag,
        ingestion_helper_tag=args.ingestion_helper_tag,
        dataflow_template_tag=args.dataflow_template_tag,
        dataflow_image_tag=args.dataflow_image_tag,
        template_gcs_base=args.template_bucket,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
