#!/usr/bin/env python3
"""check_terraform.py: Lint, validate, and test DCP Terraform configurations.

Usage:
    uv run infra/dcp/scripts/check_terraform.py [OPTIONS]

Options:
    --fmt        Check Terraform formatting across infra/dcp.
    --fix        Apply Terraform formatting in-place across infra/dcp.
    --validate   Validate Terraform configuration.
    --test       Discover and execute all *.tftest.hcl unit test suites.
    -h, --help   Show this help message.

Examples:
    # Run all checks (fmt, validate, test) before pushing:
    uv run infra/dcp/scripts/check_terraform.py

    # Automatically format files in-place:
    uv run infra/dcp/scripts/check_terraform.py --fix

    # Run only unit test suites:
    uv run infra/dcp/scripts/check_terraform.py --test
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import subprocess
import sys
from pathlib import Path

# Directory Paths
SCRIPT_DIR = Path(__file__).resolve().parent
TF_DIR = SCRIPT_DIR.parent
REPO_ROOT = TF_DIR.parent.parent

# Detect if running within a GitHub Actions CI environment
IS_CI = sys.platform != "win32" and os.environ.get("GITHUB_ACTIONS") == "true"


# ==============================================================================
# Low-Level Subprocess & Command Execution Helpers
# ==============================================================================


def _run_cmd(
    cmd: list[str], chdir: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Runs an external command capturing stdout and stderr as text."""
    return subprocess.run(  # noqa: S603
        cmd,
        cwd=str(chdir) if chdir else None,
        capture_output=True,
        text=True,
        check=False,
    )


def _init_terraform_dir(target_dir: Path) -> subprocess.CompletedProcess[str]:
    """Runs 'terraform init -backend=false' quietly in the given directory."""
    return _run_cmd(["terraform", f"-chdir={target_dir}", "init", "-backend=false"])


def _validate_terraform_dir(
    target_dir: Path,
) -> subprocess.CompletedProcess[str]:
    """Runs 'terraform validate' in the given directory."""
    return _run_cmd(["terraform", f"-chdir={target_dir}", "validate"])


def _format_terraform_dir(
    target_dir: Path, *, check_only: bool = True
) -> subprocess.CompletedProcess[str]:
    """Runs 'terraform fmt' either to check (-check) or format in-place."""
    cmd = ["terraform", "fmt", "-recursive"]
    if check_only:
        cmd.insert(2, "-check")
    cmd.append(str(target_dir))
    return _run_cmd(cmd)


def _test_terraform_dir(target_dir: Path) -> subprocess.CompletedProcess[str]:
    """Runs 'terraform test' in the given directory."""
    return _run_cmd(["terraform", f"-chdir={target_dir}", "test"])


# ==============================================================================
# Log Formatting & Output Parsing Helpers
# ==============================================================================


def _format_terraform_log(log_content: str) -> str:
    """Frames raw Terraform output inside clear visual delimiters."""
    return f"--- Terraform Output ---\n{log_content.strip()}\n------------------------"


def _extract_failing_files(output: str) -> list[str]:
    """Extracts unique source files mentioned in 'on <file> line <line>' error lines."""
    matches = re.findall(r"on\s+(\S+)\s+line\s+\d+", output)
    return sorted(set(matches))


def _extract_pass_count(test_output: str) -> str:
    """Extracts 'N passed' count from terraform test output."""
    match = re.search(r"(\d+ passed)", test_output)
    return match.group(1) if match else "passed"


def _format_target_label(target_dir: Path) -> str:
    """Formats a human-readable relative label for a target directory."""
    if target_dir == TF_DIR:
        return "root (infra/dcp)"
    try:
        return str(target_dir.relative_to(TF_DIR))
    except ValueError:
        return str(target_dir)


def _print_fmt_failures(stdout: str) -> None:
    """Prints formatted list of files requiring terraform fmt."""
    print("    FAILED\n")
    print("The following file(s) need formatting:")
    for raw_line in stdout.strip().splitlines():
        rel_path = Path(raw_line.strip())
        with contextlib.suppress(ValueError):
            rel_path = rel_path.relative_to(TF_DIR)
        print(f"  - {rel_path}")
    print("\nTo fix, run:\n  uv run infra/dcp/scripts/check_terraform.py --fix\n")


def _print_validation_failure(
    stage: str, result: subprocess.CompletedProcess[str]
) -> None:
    """Prints detailed log and summary for an init or validation failure."""
    raw_output = (result.stderr or result.stdout).strip()
    print(f"    FAILED ({stage} error)\n")
    print(_format_terraform_log(raw_output))
    print("")

    failing_files = _extract_failing_files(raw_output)
    if failing_files:
        print(f"Summary: Terraform {stage} failed in:")
        for f in failing_files:
            print(f"  - {f}")
    else:
        print(f"Summary: Terraform {stage} failed.")


# ==============================================================================
# GitHub Actions CI Group & Annotation Helpers
# ==============================================================================


def _ci_group_start(title: str) -> None:
    """Emits a GitHub Actions collapsible log group marker if in CI."""
    if IS_CI:
        print(f"::group::{title}")


def _ci_group_end() -> None:
    """Ends a GitHub Actions collapsible log group if in CI."""
    if IS_CI:
        print("::endgroup::")


def _ci_error(title: str, message: str) -> None:
    """Emits a GitHub Actions error annotation if in CI."""
    if IS_CI:
        print(f"::error title={title}::{message}")


# ==============================================================================
# Test Suite Discovery & Runner Helpers
# ==============================================================================


def _discover_test_suites(tf_dir: Path) -> list[tuple[Path, list[Path]]]:
    """Discovers all 'tests/' directories containing *.tftest.hcl files.

    Returns a list of tuples: (target_directory, [test_files]).
    """
    suites: list[tuple[Path, list[Path]]] = []

    # Find all directories named 'tests' ignoring any .terraform cache directories
    test_dirs = sorted(
        p for p in tf_dir.rglob("tests") if p.is_dir() and ".terraform" not in p.parts
    )

    for test_dir in test_dirs:
        test_files = sorted(test_dir.glob("*.tftest.hcl"))
        if test_files:
            target_dir = test_dir.parent
            suites.append((target_dir, test_files))

    return suites


def _run_single_test_suite(
    target_dir: Path,
) -> tuple[bool, str]:
    """Initializes provider plugins quietly and runs terraform test in target_dir.

    Returns (success, output_string).
    """
    init_result = _init_terraform_dir(target_dir)
    if init_result.returncode != 0:
        return False, (init_result.stderr or init_result.stdout).strip()

    test_result = _test_terraform_dir(target_dir)
    output = (test_result.stdout + "\n" + test_result.stderr).strip()
    return test_result.returncode == 0, output


def _report_test_suite_result(
    rel_target: str,
    test_files: list[Path],
    test_output: str,
    *,
    success: bool,
) -> bool:
    """Prints formatted results for a single test suite execution."""
    if success:
        pass_count = _extract_pass_count(test_output)
        print(f"    {rel_target}:")
        for tf_file in test_files:
            print(f"      {tf_file.name} ({pass_count}) ... OK")
        return True

    _ci_error("Terraform Test Failure", f"Tests failed in {rel_target}")
    print(f"    {rel_target}: FAILED\n")
    print(_format_terraform_log(test_output))
    print("")
    return False


# ==============================================================================
# Public Check Operations: Format, Validate, Test
# ==============================================================================


def run_fmt() -> bool:
    """Checks Terraform formatting across TF_DIR."""
    print("==> Checking formatting...")
    result = _format_terraform_dir(TF_DIR, check_only=True)
    if result.returncode == 0:
        print("    OK")
        return True

    _print_fmt_failures(result.stdout)
    return False


def run_fix() -> bool:
    """Formats all Terraform files in TF_DIR in-place."""
    print("==> Formatting files in place...")
    result = _format_terraform_dir(TF_DIR, check_only=False)
    if result.returncode == 0:
        print("    OK")
        return True

    print(f"ERROR: Formatting failed:\n{result.stderr or result.stdout}")
    return False


def run_validate() -> bool:
    """Initializes and validates Terraform configuration in TF_DIR."""
    print("==> Validating Terraform...")

    # 1. Initialize modules and providers quietly
    init_result = _init_terraform_dir(TF_DIR)
    if init_result.returncode != 0:
        _print_validation_failure("initialization", init_result)
        return False

    # 2. Validate configuration
    val_result = _validate_terraform_dir(TF_DIR)
    if val_result.returncode == 0:
        print("    OK")
        return True

    _print_validation_failure("validation", val_result)
    return False


def run_tests() -> bool:
    """Discovers and executes all Terraform unit test suites across TF_DIR."""
    print("==> Running unit tests...")
    suites = _discover_test_suites(TF_DIR)

    if not suites:
        print("    No tests found.")
        return True

    failed_targets: list[str] = []

    for target_dir, test_files in suites:
        rel_target = _format_target_label(target_dir)
        _ci_group_start(f"[terraform test] {rel_target}")

        success, test_output = _run_single_test_suite(target_dir)
        if not _report_test_suite_result(
            rel_target, test_files, test_output, success=success
        ):
            failed_targets.append(rel_target)

        _ci_group_end()

    if failed_targets:
        print(f"Summary: Tests failed in: {', '.join(failed_targets)}")
        return False

    print("==> All tests passed.")
    return True


def run_all_checks() -> bool:
    """Executes all checks sequentially (fmt, validate, test).

    Surfaces all formatting and validation issues, skipping tests only if
    validation fails.
    """
    has_error = False

    if not run_fmt():
        has_error = True

    if run_validate():
        if not run_tests():
            has_error = True
    else:
        has_error = True
        print("==> Skipping unit tests because validation failed.")

    return not has_error


# ==============================================================================
# CLI Entrypoint & Argument Parsing
# ==============================================================================


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Lint, validate, and test DCP Terraform configurations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--fmt",
        action="store_true",
        help="Check Terraform formatting across infra/dcp.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply Terraform formatting in-place across infra/dcp.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate Terraform configuration.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Discover and execute all *.tftest.hcl unit test suites.",
    )
    return parser.parse_args()


def main() -> int:
    """Main CLI dispatch entrypoint."""
    args = parse_args()

    # Specific flag execution
    if args.fix:
        return 0 if run_fix() else 1
    if args.fmt:
        return 0 if run_fmt() else 1
    if args.validate:
        return 0 if run_validate() else 1
    if args.test:
        return 0 if run_tests() else 1

    # Default: run all checks
    return 0 if run_all_checks() else 1


if __name__ == "__main__":
    sys.exit(main())
