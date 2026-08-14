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

"""apply_version_bump.py - Single Source of Truth for CI/CD Version Updates.

PURPOSE:
  Applies local version updates across:
    1. Root VERSION file & subpackage packages/*/VERSION files.
    2. Terraform HCL variable defaults (dcp_version) in infra/dcp/*.tf.
    3. Lockstep dependency requirement in packages/datacommons-cli/pyproject.toml
       (datacommons-admin==NEW_VERSION).

USAGE ACROSS CI/CD FLOWS:
  1. Staging / Release Candidate (deploy/staging.yaml):
     Runs this script ephemerally inside Cloud Build on target commit,
     tags and pushes v<VERSION> to GitHub (for remote Terraform template fetches),
     and publishes candidate wheels to TestPyPI. (No Git commits pushed to main).

  2. Main Branch Version Bump PR (deploy/bump_version.yaml):
     Runs this script on main, updates uv.lock, commits modified files,
     and opens an automated PR against main.

  3. Production Release (deploy/release.yaml):
     Does NOT run this script (the bump PR in step 2 should have already been merged).
     Performs read-only validation that Git source code already matches tag_version
     before building and publishing official wheels to PyPI.
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def apply_version_bump(new_version: str) -> None:
    """Updates version manifests and dependency pins across the monorepo."""
    version_file = REPO_ROOT / "VERSION"
    old_version = (
        version_file.read_text().strip() if version_file.exists() else "unknown"
    )
    print(f"Applying version bump: '{old_version}' -> '{new_version}'...")

    # 1. Update root VERSION file
    version_file.write_text(f"{new_version}\n")

    # 2. Update subpackage VERSION files
    packages_dir = REPO_ROOT / "packages"
    if packages_dir.is_dir():
        for pkg_dir in sorted(packages_dir.iterdir()):
            if pkg_dir.is_dir() and (pkg_dir / "pyproject.toml").is_file():
                pkg_version_file = pkg_dir / "VERSION"
                rel_path = pkg_version_file.relative_to(REPO_ROOT)
                print(f"Updating {rel_path} to {new_version}")
                pkg_version_file.write_text(f"{new_version}\n")

    # 3. Update Terraform dcp_version variable default in infra/dcp/variables.tf
    tf_file = REPO_ROOT / "infra/dcp/variables.tf"
    if tf_file.exists():
        tf_content = tf_file.read_text()
        updated_tf, count = re.subn(
            r'(variable\s+"dcp_version"\s+{[^}]*default\s*=\s*")[^"]+(")',
            rf"\g<1>{new_version}\g<2>",
            tf_content,
        )
        if not count:
            sys.exit(
                "Error: variable 'dcp_version' default not found or updated in"
                " infra/dcp/variables.tf"
            )
        tf_file.write_text(updated_tf)

    # 4. Lock datacommons-admin dependency requirement in datacommons-cli/pyproject.toml
    cli_toml = REPO_ROOT / "packages/datacommons-cli/pyproject.toml"
    if cli_toml.exists():
        toml_content = cli_toml.read_text()
        updated_toml, count = re.subn(
            r'"datacommons-admin(?:\s*[=><~][^"]*)?"',
            f'"datacommons-admin=={new_version}"',
            toml_content,
        )
        if not count:
            sys.exit(
                "Error: datacommons-admin dependency not found or updated in"
                " packages/datacommons-cli/pyproject.toml"
            )
        cli_toml.write_text(updated_toml)

    print(f"Successfully applied version bump to '{new_version}'.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Single Source of Truth for DCP Version Updates."
    )
    parser.add_argument(
        "new_version",
        help="The target version string (e.g. 1.2.3 or 1.2.3rc1)",
    )
    args = parser.parse_args()
    apply_version_bump(args.new_version)


if __name__ == "__main__":
    main()
