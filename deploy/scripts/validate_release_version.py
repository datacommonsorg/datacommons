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
  Validates that all monorepo version declarations and dependency pins strictly
  match the target release version tag before publishing packages to PyPI.

CHECKS PERFORMED:
  1. Root VERSION file matches target version.
  2. All subpackage packages/*/VERSION files match target version.
  3. packages/datacommons-cli/pyproject.toml locks datacommons-admin to ==target_version.
  4. infra/dcp/variables.tf declares dcp_version default matching target_version.

USAGE:
  python3 deploy/scripts/validate_release_version.py <TAG_OR_VERSION>
  Example:
    python3 deploy/scripts/validate_release_version.py 1.2.3
    python3 deploy/scripts/validate_release_version.py v1.2.3
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def validate_release_version(tag_or_version: str) -> None:
    """Validates all version declarations match the target release version."""
    target_version = tag_or_version.strip().lstrip("v").strip()
    if not target_version:
        sys.exit("Error: Target version cannot be empty.")

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

    # 3. Validate datacommons-cli pyproject.toml lockstep dependency pin
    cli_toml = REPO_ROOT / "packages/datacommons-cli/pyproject.toml"
    if not cli_toml.exists():
        errors.append("packages/datacommons-cli/pyproject.toml does not exist.")
    else:
        toml_content = cli_toml.read_text()
        m = re.search(r'["\']datacommons-admin\s*==\s*([^"\']+)["\']', toml_content)
        if not m:
            errors.append(
                f"packages/datacommons-cli/pyproject.toml does not lock"
                f" datacommons-admin=={target_version}."
            )
        elif m.group(1) != target_version:
            errors.append(
                f"packages/datacommons-cli/pyproject.toml locks datacommons-admin to"
                f" '{m.group(1)}' instead of target '{target_version}'."
            )
        else:
            print(
                f"  [OK] packages/datacommons-cli/pyproject.toml:"
                f" datacommons-admin=={target_version}"
            )

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
    args = parser.parse_args()
    validate_release_version(args.tag_or_version)


if __name__ == "__main__":
    main()
