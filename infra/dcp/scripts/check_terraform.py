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

"""check_terraform.py: Format, validate, and test Terraform configurations.

Usage:
    uv run infra/dcp/scripts/check_terraform.py [OPTIONS]
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TF_DIR = SCRIPT_DIR.parent

DIVIDER = "─" * 70
SUMMARY_DIVIDER = "=" * 70

USE_COLOR = (os.environ.get("NO_COLOR") is None) and (
    sys.stdout.isatty() or os.environ.get("GITHUB_ACTIONS") == "true"
)


def _color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


PASSED = _color("✓ Passed", "1;32")
FAILED = _color("✖ Failed", "1;31")
RED_BAR = _color("│", "31")
FAIL_ICON = _color("✖", "1;31")

FailureEntry = tuple[str, list[str]]


def _print_header(title: str) -> None:
    print(f"{DIVIDER}\n {title}\n{DIVIDER}")


def _run_step(
    args: list[str],
    chdir: Path,
) -> tuple[bool, subprocess.CompletedProcess[str]]:
    """Builds `terraform -chdir=<rel_dir> ...` relative to cwd, prints it, and executes it."""
    rel_dir = os.path.relpath(chdir.resolve(), Path.cwd().resolve())
    chdir_arg = [f"-chdir={rel_dir}"] if rel_dir != "." else []
    cmd = ["terraform", *chdir_arg, *args]
    print(f"$ {shlex.join(cmd)}")

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(f"{FAILED}\n")
        output = res.stderr.strip() or res.stdout.strip()
        if output:
            if "│" not in output:
                output = textwrap.indent(output, f"{RED_BAR} ", lambda _: True)
            print(f"{output}\n")
        return False, res

    if args[0] != "init":
        print(PASSED)
        out = res.stdout.rstrip().removesuffix("\033[0m").strip()
        if out:
            print(textwrap.indent(out, "  │ ", lambda _: True))
        print("")
    return True, res


def _discover_test_suites(tf_dir: Path) -> list[Path]:
    """Returns module directories under tf_dir that contain tests/*.tftest.hcl."""
    resolved_script_dir = SCRIPT_DIR.resolve()
    return [
        test_dir.parent
        for test_dir in sorted(tf_dir.rglob("tests"))
        if test_dir.is_dir()
        and ".terraform" not in test_dir.parts
        and not test_dir.resolve().is_relative_to(resolved_script_dir)
        and any(test_dir.glob("*.tftest.hcl"))
    ]


def run_fix(tf_dir: Path) -> bool:
    """Formats all Terraform files in tf_dir in-place."""
    _print_header("Formatting In-Place")
    ok, _ = _run_step(["fmt", "-recursive"], tf_dir)
    return ok


def run_fmt(failures: list[FailureEntry], tf_dir: Path) -> None:
    """Checks Terraform formatting across tf_dir."""
    _print_header("Formatting")
    ok, res = _run_step(["fmt", "-check", "-recursive"], tf_dir)
    if not ok:
        files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        failures.append(("Formatting (re-run with --fix)", files))


def run_validate(failures: list[FailureEntry], tf_dir: Path) -> None:
    """Initializes and validates Terraform configuration in tf_dir."""
    _print_header("Validation")
    init_ok, _ = _run_step(["init", "-backend=false"], tf_dir)
    if not init_ok or not _run_step(["validate"], tf_dir)[0]:
        failures.append(("Validation", []))


def run_tests(failures: list[FailureEntry], tf_dir: Path) -> None:
    """Discovers and executes all Terraform unit test suites across tf_dir."""
    _print_header("Unit Tests")
    suites = _discover_test_suites(tf_dir)
    if not suites:
        print(f"{FAILED}\n\nERROR: No *.tftest.hcl test suites found.\n")
        failures.append(("Unit Tests", ["no test suites found"]))
        return

    failed_modules: list[str] = []
    for target_dir in suites:
        rel_target = os.path.relpath(target_dir.resolve(), tf_dir.resolve())
        init_ok, _ = _run_step(["init", "-backend=false"], target_dir)
        if not init_ok or not _run_step(["test"], target_dir)[0]:
            failed_modules.append(rel_target)

    if failed_modules:
        failures.append(("Unit Tests", failed_modules))


def _print_summary(failures: list[FailureEntry]) -> None:
    if not failures:
        print(f"{SUMMARY_DIVIDER}\n Summary: {PASSED}\n{DIVIDER}\n")
        return

    print(f"{SUMMARY_DIVIDER}\n Summary: {FAILED}\n{DIVIDER}\n")
    for heading, items in failures:
        print(f"  {FAIL_ICON} {heading}")
        for item in items:
            print(f"      - {item}")
    print(f"\n{DIVIDER}\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tf-dir",
        type=Path,
        default=TF_DIR,
        help="Target Terraform directory (default: infra/dcp).",
    )
    parser.add_argument(
        "--fmt", action="store_true", help="Check Terraform formatting."
    )
    parser.add_argument(
        "--fix", action="store_true", help="Format Terraform files in-place."
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate Terraform configuration."
    )
    parser.add_argument(
        "--test", action="store_true", help="Run *.tftest.hcl unit test suites."
    )
    args = parser.parse_args(argv)
    if args.fix and (args.fmt or args.validate or args.test):
        parser.error("--fix cannot be combined with --fmt, --validate, or --test")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if shutil.which("terraform") is None:
        print(
            f"{FAILED} 'terraform' binary not found on PATH. "
            "Install Terraform (>= 1.7.0): https://developer.hashicorp.com/terraform/install",
            file=sys.stderr,
        )
        return 2

    tf_dir = args.tf_dir.resolve()
    if args.fix:
        return 0 if run_fix(tf_dir) else 1

    run_all = not (args.fmt or args.validate or args.test)
    failures: list[FailureEntry] = []
    if run_all or args.fmt:
        run_fmt(failures, tf_dir)
    if run_all or args.validate:
        run_validate(failures, tf_dir)
    if run_all or args.test:
        run_tests(failures, tf_dir)

    _print_summary(failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
