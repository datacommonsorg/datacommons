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
  distribution. datacommons-admin MUST be published before datacommons-cli
  due to the lockstep dependency pin (datacommons-admin==VERSION).

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
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# SINGLE SOURCE OF TRUTH: Authoritative list and order of packages for distribution.
# datacommons-admin MUST be published before datacommons-cli.
PUBLISHED_PACKAGES = [
    "datacommons-admin",
    "datacommons-cli",
]

TEST_PYPI_URL = "https://test.pypi.org/legacy/"


def _get_venv_bin(venv_dir: Path, bin_name: str) -> Path:
    bin_folder = "Scripts" if sys.platform == "win32" else "bin"
    suffix = ".exe" if sys.platform == "win32" else ""
    return venv_dir / bin_folder / f"{bin_name}{suffix}"


def _build_wheels(tmp_dist_dir: Path) -> None:
    """Builds wheels and sdists for all published packages into tmp_dist_dir."""
    print("========================================================================")
    print("[1/4] Building packages into temporary clean-room directory...")
    print("========================================================================")
    for pkg_name in PUBLISHED_PACKAGES:
        pkg_dir = REPO_ROOT / "packages" / pkg_name
        if not pkg_dir.is_dir() or not (pkg_dir / "pyproject.toml").is_file():
            sys.exit(
                f"Error: Package directory 'packages/{pkg_name}' does not exist or is"
                " missing pyproject.toml."
            )

        print(f"  -> Building {pkg_name}...")
        result = subprocess.run(
            ["uv", "build", "--out-dir", str(tmp_dist_dir)],
            cwd=pkg_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"\n❌ BUILD FAILED for package '{pkg_name}':\n{result.stderr}")
            sys.exit(1)
    print("  ✓ All package wheels built successfully.\n")


def _verify_packages(tmp_dist_dir: Path, tmp_venv_dir: Path) -> None:
    """Provisions isolated venv, installs from tmp_dist_dir, and runs smoke tests."""
    print("========================================================================")
    print("[2/4] Provisioning isolated sandbox virtualenv...")
    print("========================================================================")
    venv_res = subprocess.run(
        ["uv", "venv", str(tmp_venv_dir)],
        capture_output=True,
        text=True,
        cwd=tmp_dist_dir.parent,
        check=False,
    )
    if venv_res.returncode != 0:
        print(f"❌ Failed to create sandbox venv:\n{venv_res.stderr}")
        sys.exit(1)

    venv_python = _get_venv_bin(tmp_venv_dir, "python")

    print("========================================================================")
    print("[3/4] Pre-publish verification: testing resolution & installation...")
    print("========================================================================")
    built_wheels = sorted([str(w) for w in tmp_dist_dir.glob("*.whl")])
    if not built_wheels:
        sys.exit(f"Error: No wheels found in {tmp_dist_dir} for verification.")

    install_cmd = [
        "uv",
        "pip",
        "install",
        "--python",
        str(venv_python),
        "--find-links",
        str(tmp_dist_dir),
        *built_wheels,
    ]
    install_res = subprocess.run(
        install_cmd,
        capture_output=True,
        text=True,
        cwd=tmp_dist_dir.parent,  # CWD outside repo to prevent sys.path leakage
        check=False,
    )
    if install_res.returncode != 0:
        print("\n" + "=" * 72)
        print("❌ PRE-PUBLISH VERIFICATION FAILED: Dependency Resolution / Install Error")
        print("=" * 72)
        print(install_res.stderr or install_res.stdout)
        print("\nAborting release. No packages were uploaded.")
        sys.exit(1)
    print("  ✓ All packages and dependencies installed successfully in sandbox.")

    # Smoke Test Layer 1: Universal Module Imports (tests all packages)
    print("\n  -> Testing module imports and runtime assets...")
    module_imports = "; ".join(
        [f"import {pkg.replace('-', '_')}" for pkg in PUBLISHED_PACKAGES]
    )
    import_res = subprocess.run(
        [str(venv_python), "-I", "-c", module_imports],
        capture_output=True,
        text=True,
        cwd=tmp_dist_dir.parent,
        check=False,
    )
    if import_res.returncode != 0:
        print("\n" + "=" * 72)
        print("❌ PRE-PUBLISH VERIFICATION FAILED: Module Import / Runtime Asset Error")
        print("=" * 72)
        print(import_res.stderr or import_res.stdout)
        print("\nAborting release. No packages were uploaded.")
        sys.exit(1)
    print("  ✓ Module imports succeeded.")

    # Smoke Test Layer 2: CLI Console Scripts (for CLI packages)
    cli_bin = _get_venv_bin(tmp_venv_dir, "datacommons")
    if cli_bin.exists():
        print("  -> Testing CLI console scripts...")
        for cmd_args in [["--version"], ["--help"], ["admin", "--help"]]:
            cli_res = subprocess.run(
                [str(cli_bin), *cmd_args],
                capture_output=True,
                text=True,
                cwd=tmp_dist_dir.parent,
                check=False,
            )
            if cli_res.returncode != 0:
                print("\n" + "=" * 72)
                print(
                    f"❌ PRE-PUBLISH VERIFICATION FAILED: CLI command 'datacommons {' '.join(cmd_args)}' crashed"
                )
                print("=" * 72)
                print(cli_res.stderr or cli_res.stdout)
                print("\nAborting release. No packages were uploaded.")
                sys.exit(1)
        print("  ✓ CLI entrypoints verified successfully.\n")


def _publish_wheels(tmp_dist_dir: Path, target: str, token: str) -> None:
    """Publishes verified wheel and sdist artifacts in strict topological order."""
    print("========================================================================")
    print(
        f"[4/4] Publishing verified packages to {target.upper()} in topological"
        " order..."
    )
    print("========================================================================")
    for pkg_name in PUBLISHED_PACKAGES:
        pkg_dist_name = pkg_name.replace("-", "_")
        artifacts = sorted(
            list(tmp_dist_dir.glob(f"{pkg_dist_name}-*.whl"))
            + list(tmp_dist_dir.glob(f"{pkg_dist_name}-*.tar.gz"))
        )
        if not artifacts:
            sys.exit(
                f"Error: No built artifacts found in {tmp_dist_dir} for {pkg_name}."
            )

        print(f"[{pkg_name}] Publishing {len(artifacts)} artifact(s) to {target}...")
        publish_cmd = ["uv", "publish"]
        if target == "testpypi":
            publish_cmd.extend(["--publish-url", TEST_PYPI_URL])
        publish_cmd.extend([str(a) for a in artifacts])

        env = {**os.environ, "UV_PUBLISH_TOKEN": token}
        res = subprocess.run(
            publish_cmd,
            env=env,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        if res.returncode != 0:
            print(f"\n❌ Failed to publish {pkg_name} to {target}:\n{res.stderr}")
            sys.exit(1)
        print(f"[{pkg_name}] ✓ Successfully published to {target}!\n")


def publish_packages(
    target: str, token_env: str | None, *, dry_run: bool = False
) -> None:
    """Builds, verifies in a clean sandbox, and publishes packages."""
    token = None
    if not dry_run:
        if not token_env:
            sys.exit("Error: --token-env is required unless --dry-run is specified.")
        token = os.environ.get(token_env)
        if not token:
            sys.exit(f"Error: Environment variable '{token_env}' is not set or empty.")

    print(
        f"Publishing {len(PUBLISHED_PACKAGES)} package(s) to "
        f"{'[DRY RUN - VERIFY ONLY]' if dry_run else target.upper()} in topological"
        " order:\n"
    )
    for idx, pkg_name in enumerate(PUBLISHED_PACKAGES, 1):
        print(f"  {idx}. {pkg_name}")
    print()

    with tempfile.TemporaryDirectory(prefix="dcp-publish-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        tmp_dist_dir = tmp_dir / "dist"
        tmp_venv_dir = tmp_dir / "venv"
        tmp_dist_dir.mkdir()

        # Step 1: Build all wheels into temporary dist
        _build_wheels(tmp_dist_dir)

        # Step 2 & 3: Clean-room sandbox verification
        _verify_packages(tmp_dist_dir, tmp_venv_dir)

        # Step 4: Publish verified artifacts (or finish dry run)
        if dry_run:
            print(
                "✨ [DRY RUN] Clean-room pre-publish verification succeeded for all"
                " packages."
            )
            print("   No packages were uploaded.\n")
            return

        _publish_wheels(tmp_dist_dir, target, token)

    print("All packages verified and published successfully!")


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
        help="Build and verify packages without uploading to index.",
    )
    args = parser.parse_args()

    publish_packages(target=args.target, token_env=args.token_env, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
