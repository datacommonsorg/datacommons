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

"""validate_release_version.py - Pre-publish Version Consistency Validator.

PURPOSE:
  Validates that all monorepo version declarations, dependency pins, container
  images, and Dataflow Flex Templates strictly match the target release version
  tag before publishing packages to PyPI.

CHECKS PERFORMED:
  1. Release tag/version matches SemVer / PEP 440 format.
  2. Root VERSION file matches target version.
  3. All subpackage packages/*/VERSION files match target version.
  4. packages/datacommons-cli/pyproject.toml locks datacommons-admin to ==target_version.
  5. infra/dcp/variables.tf declares dcp_version default matching target_version.
  6. (Optional/CI via --check-remote-artifacts) All 5 container images exist in GCR/Artifact Registry.
  7. (Optional/CI via --check-remote-artifacts) Dataflow Flex Template spec exists in GCS.

NOTE ON INTENTIONAL SELF-CONTAINMENT:
  This script is intentionally self-contained with zero local helper imports so that
  it can be executed reliably in any isolated CI/CD container without sys.path
  configuration. The version validation pattern is synchronized with apply_version_bump.py;
  if you modify the version format pattern here, please check if apply_version_bump.py
  needs the same update.

USAGE:
  python3 deploy/scripts/validate_release_version.py <TAG_OR_VERSION>
  Example:
    python3 deploy/scripts/validate_release_version.py 1.2.3
    python3 deploy/scripts/validate_release_version.py v1.2.3 --check-remote-artifacts
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Anchored SemVer / PEP 440 regex matching standard releases (1.2.3), pre-releases
# (1.2.3rc1, 1.2.3a1, 1.2.3b1), and development versions (1.2.0.dev0).
# Synchronized with apply_version_bump.py.
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?(?:\.dev\d+)?$")

LOCKSTEP_DEPENDENCIES = [
    ("packages/datacommons-admin/pyproject.toml", "datacommons-db"),
    ("packages/datacommons-cli/pyproject.toml", "datacommons-admin"),
]

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

DEFAULT_TEMPLATE_GCS_BASE = DATAFLOW_CONFIG["template_gcs_base"]


def validate_release_version(
    tag_or_version: str,
    *,
    check_remote_artifacts: bool = False,
    template_gcs_base: str = DEFAULT_TEMPLATE_GCS_BASE,
) -> None:
    """Validates all version declarations match the target release version."""
    target_version = tag_or_version.strip().lstrip("v").strip()
    if not target_version:
        sys.exit("Error: Target version cannot be empty.")
    if not VERSION_PATTERN.match(target_version):
        sys.exit(
            f"Error: Invalid release tag/version format '{tag_or_version}'. "
            "Must follow SemVer / PEP 440 (e.g. '1.2.3', 'v1.2.3', or '1.2.3rc1')."
        )

    errors: list[str] = []
    print(
        f"Validating monorepo version consistency against target '{target_version}'..."
    )

    # 1. Validate root VERSION file
    root_version_file = REPO_ROOT / "VERSION"
    if not root_version_file.exists():
        errors.append("Root VERSION file does not exist.")
    else:
        root_v = root_version_file.read_text().strip()
        if root_v != target_version:
            errors.append(
                f"Root VERSION file ({root_v}) does not match target version"
                f" ({target_version})."
            )
        else:
            print(f"  [OK] Root VERSION: {root_v}")

    # 2. Validate subpackage VERSION files
    packages_dir = REPO_ROOT / "packages"
    pkg_dirs = (
        [
            d
            for d in sorted(packages_dir.iterdir())
            if d.is_dir() and (d / "pyproject.toml").is_file()
        ]
        if packages_dir.is_dir()
        else []
    )
    if not pkg_dirs:
        errors.append(
            "No package directories with pyproject.toml found under packages/."
        )
    else:
        for pkg_dir in pkg_dirs:
            pkg_vf = pkg_dir / "VERSION"
            rel_path = pkg_vf.relative_to(REPO_ROOT)
            if not pkg_vf.is_file():
                errors.append(f"Required version file {rel_path} is missing.")
            else:
                pkg_v = pkg_vf.read_text().strip()
                if pkg_v != target_version:
                    errors.append(
                        f"{rel_path} ({pkg_v}) does not match target version"
                        f" ({target_version})."
                    )
                else:
                    print(f"  [OK] {rel_path}: {pkg_v}")

    # 3. Validate lockstep dependency pins in subpackages
    for manifest_rel_path, dep_pkg in LOCKSTEP_DEPENDENCIES:
        manifest_file = REPO_ROOT / manifest_rel_path
        if not manifest_file.exists():
            errors.append(f"{manifest_rel_path} does not exist.")
            continue
        content = manifest_file.read_text()
        m = re.search(
            rf'["\']{re.escape(dep_pkg)}\s*==\s*([^"\']+)["\']',
            content,
        )
        if not m:
            errors.append(
                f"{manifest_rel_path} does not lock {dep_pkg}=={target_version}."
            )
        elif m.group(1) != target_version:
            errors.append(
                f"{manifest_rel_path} locks {dep_pkg} to '{m.group(1)}' instead of target '{target_version}'."
            )
        else:
            print(f"  [OK] {manifest_rel_path}: {dep_pkg}=={target_version}")

    # 4. Validate Terraform dcp_version default in infra/dcp/variables.tf
    tf_file = REPO_ROOT / "infra/dcp/variables.tf"
    if not tf_file.exists():
        errors.append("infra/dcp/variables.tf does not exist.")
    else:
        tf_content = tf_file.read_text()
        m = re.search(
            r'variable\s+"dcp_version"\s+{[^}]*default\s*=\s*"([^"]+)"',
            tf_content,
        )
        if not m:
            errors.append(
                "Could not find variable 'dcp_version' default in"
                " infra/dcp/variables.tf."
            )
        elif m.group(1) != target_version:
            errors.append(
                f"infra/dcp/variables.tf dcp_version default ({m.group(1)}) does not"
                f" match target version ({target_version})."
            )
        else:
            print(f"  [OK] infra/dcp/variables.tf (dcp_version default): {m.group(1)}")

    # 5. Optional / CI: Validate remote release artifacts (images & GCS template)
    if check_remote_artifacts:
        print("\nValidating remote release artifacts exist...")
        if not shutil.which("gcloud"):
            errors.append(
                "'gcloud' CLI tool is required for remote artifact validation"
                " but was not found in PATH."
            )
        else:
            # A. Check standard Cloud Run container images in GCR
            for artifact, repo in CONTAINER_IMAGE_MAP.items():
                image_ref = f"{repo}:{target_version}"
                cmd = [
                    "gcloud",
                    "container",
                    "images",
                    "describe",
                    image_ref,
                    "--format=json",
                ]
                res = subprocess.run(cmd, check=False, capture_output=True, text=True)
                if res.returncode != 0:
                    detail = (
                        f" Details: {res.stderr.strip()}" if res.stderr.strip() else ""
                    )
                    errors.append(
                        f"Remote container image '{image_ref}' does not exist"
                        f" in registry.{detail}"
                    )
                else:
                    print(f"  [OK] Container Image ({artifact}): {image_ref}")

            # B. Check Dataflow worker container image in Artifact Registry
            df_image_ref = f"{DATAFLOW_CONFIG['image_repo']}:{target_version}"
            cmd = [
                "gcloud",
                "artifacts",
                "docker",
                "images",
                "describe",
                df_image_ref,
                "--format=json",
            ]
            res = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if res.returncode != 0:
                detail = f" Details: {res.stderr.strip()}" if res.stderr.strip() else ""
                errors.append(
                    f"Dataflow worker container image '{df_image_ref}' does not exist in Artifact Registry.{detail}"
                )
            else:
                print(f"  [OK] Dataflow Worker Image: {df_image_ref}")

            # C. Check Dataflow Flex Template spec in GCS
            template_uri = (
                f"{template_gcs_base.rstrip('/')}/ingestion-{target_version}.json"
            )
            cmd = ["gcloud", "storage", "ls", template_uri]
            res = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if res.returncode != 0:
                detail = f" Details: {res.stderr.strip()}" if res.stderr.strip() else ""
                errors.append(
                    f"Dataflow Flex Template spec '{template_uri}' does not"
                    f" exist in GCS.{detail}"
                )
            else:
                print(f"  [OK] Dataflow Flex Template: {template_uri}")

    if errors:
        print("\nRelease validation FAILED with the following error(s):")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print(f"\nAll release version checks PASSED successfully for 'v{target_version}'.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate monorepo version consistency before release."
    )
    parser.add_argument(
        "tag_or_version",
        help="The release tag or version string (e.g. v1.2.3 or 1.2.3)",
    )
    parser.add_argument(
        "--check-remote-artifacts",
        action="store_true",
        help="Validate that all 5 container images and Dataflow Flex Template exist in remote registries/GCS.",
    )
    parser.add_argument(
        "--template-bucket",
        default=DEFAULT_TEMPLATE_GCS_BASE,
        help=f"GCS bucket directory for Dataflow Flex Templates (default: {DEFAULT_TEMPLATE_GCS_BASE}).",
    )
    args = parser.parse_args()
    validate_release_version(
        tag_or_version=args.tag_or_version,
        check_remote_artifacts=args.check_remote_artifacts,
        template_gcs_base=args.template_bucket,
    )


if __name__ == "__main__":
    main()
