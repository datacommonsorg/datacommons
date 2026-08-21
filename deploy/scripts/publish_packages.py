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

"""publish_packages.py - Package Builder & PyPI / TestPyPI Distribution Script.

PURPOSE:
  Builds and publishes official Data Commons Platform (DCP) Python packages
  to PyPI or TestPyPI in strict topological dependency order.

SINGLE SOURCE OF TRUTH:
  PUBLISHED_PACKAGES defines the authoritative list and build order for public
  distribution. datacommons-db MUST be published before datacommons-admin,
  and datacommons-admin MUST be published before datacommons-cli due to
  lockstep dependency pins (datacommons-db==VERSION, datacommons-admin==VERSION).

USAGE:
  python3 deploy/scripts/publish_packages.py --target <pypi|testpypi> --token-env <ENV_VAR_NAME>

  Examples:
    # Publish to TestPyPI
    python3 deploy/scripts/publish_packages.py --target testpypi --token-env TEST_PYPI_TOKEN

    # Publish to Official PyPI
    python3 deploy/scripts/publish_packages.py --target pypi --token-env PYPI_TOKEN

    # Dry-run build only without uploading
    python3 deploy/scripts/publish_packages.py --dry-run
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# SINGLE SOURCE OF TRUTH: Authoritative list and order of packages for distribution.
# datacommons-db MUST be published before datacommons-admin, and datacommons-admin
# MUST be published before datacommons-cli.
PUBLISHED_PACKAGES = [
    "datacommons-db",
    "datacommons-admin",
    "datacommons-cli",
]

TEST_PYPI_URL = "https://test.pypi.org/legacy/"


def publish_packages(
    target: str, token_env: str | None, *, dry_run: bool = False
) -> None:
    """Builds and publishes packages in topological order."""
    token = None
    if not dry_run:
        if not token_env:
            sys.exit("Error: --token-env is required unless --dry-run is specified.")
        token = os.environ.get(token_env)
        if not token:
            sys.exit(f"Error: Environment variable '{token_env}' is not set or empty.")

    print(
        f"Publishing {len(PUBLISHED_PACKAGES)} package(s) to"
        f" {'[DRY RUN - BUILD ONLY]' if dry_run else target.upper()} in topological"
        " order:\n"
    )
    for idx, pkg_name in enumerate(PUBLISHED_PACKAGES, 1):
        print(f"  {idx}. {pkg_name}")
    print()

    for pkg_name in PUBLISHED_PACKAGES:
        pkg_dir = REPO_ROOT / "packages" / pkg_name
        if not pkg_dir.is_dir() or not (pkg_dir / "pyproject.toml").is_file():
            sys.exit(
                f"Error: Package directory 'packages/{pkg_name}' does not exist or is"
                " missing pyproject.toml."
            )

        print(
            "========================================================================"
        )
        print(f"[{pkg_name}] Building package...")
        print(
            "========================================================================"
        )

        # 1. Clean previous build artifacts
        for artifact_name in ["dist", "build"]:
            artifact_path = pkg_dir / artifact_name
            if artifact_path.exists():
                shutil.rmtree(artifact_path)
        for egg_info in pkg_dir.glob("*.egg-info"):
            if egg_info.is_dir():
                shutil.rmtree(egg_info)

        # 2. Build distribution wheel and sdist with uv
        # Dynamically pin dependencies on internal packages to the release version
        # during build, then restore pyproject.toml to avoid hardcoding in git.
        pyproject_file = pkg_dir / "pyproject.toml"
        version_file = pkg_dir / "VERSION"
        pkg_version = (
            version_file.read_text().strip()
            if version_file.is_file()
            else (REPO_ROOT / "VERSION").read_text().strip()
        )
        original_toml = pyproject_file.read_text()
        try:
            modified_toml = original_toml
            for dep_pkg in PUBLISHED_PACKAGES:
                if dep_pkg != pkg_name:
                    modified_toml = re.sub(
                        rf'"{re.escape(dep_pkg)}(?:\s*[=><~][^"]*)?"',
                        f'"{dep_pkg}=={pkg_version}"',
                        modified_toml,
                    )
            if modified_toml != original_toml:
                pyproject_file.write_text(modified_toml)

            subprocess.run(
                ["uv", "build", "--out-dir", "dist"],
                cwd=pkg_dir,
                check=True,
            )
        finally:
            if pyproject_file.read_text() != original_toml:
                pyproject_file.write_text(original_toml)

        print(f"[{pkg_name}] Build completed successfully.")

        # 3. Publish to PyPI / TestPyPI
        if dry_run:
            print(f"[{pkg_name}] DRY RUN: Skipping publish step.\n")
            continue

        print(f"[{pkg_name}] Publishing to {target}...")
        publish_cmd = ["uv", "publish"]
        if target == "testpypi":
            publish_cmd.extend(["--publish-url", TEST_PYPI_URL])

        # Inject auth token via UV_PUBLISH_TOKEN in environment to avoid argv/ps exposure
        env = {**os.environ, "UV_PUBLISH_TOKEN": token}
        subprocess.run(publish_cmd, cwd=pkg_dir, env=env, check=True)
        print(f"[{pkg_name}] Successfully published to {target}!\n")

    print("All packages processed successfully!")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and publish DCP packages to PyPI or TestPyPI."
    )
    parser.add_argument(
        "--target",
        choices=["pypi", "testpypi"],
        default="pypi",
        help="Target package index (default: pypi).",
    )
    parser.add_argument(
        "--token-env",
        help=("Name of environment variable containing the PyPI/TestPyPI auth token."),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build packages without uploading to index.",
    )
    args = parser.parse_args()

    publish_packages(target=args.target, token_env=args.token_env, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
