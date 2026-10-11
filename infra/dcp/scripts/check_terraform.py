#!/usr/bin/env python3
"""check_terraform.py: Lint, validate, and test DCP Terraform configurations.

Usage:
    uv run infra/dcp/scripts/check_terraform.py [OPTIONS]

Options:
    --fmt        Check Terraform formatting across infra/dcp (read-only).
    --fix        Apply Terraform formatting in-place across infra/dcp.
    --validate   Validate Terraform configuration (read-only).
    --test       Discover and execute all *.tftest.hcl unit test suites (read-only).
    -h, --help   Show this help message.

Examples:
    # Run all verification checks (fmt, validate, test) before pushing:
    uv run infra/dcp/scripts/check_terraform.py

    # Automatically format files in-place:
    uv run infra/dcp/scripts/check_terraform.py --fix

    # Run only unit test suites:
    uv run infra/dcp/scripts/check_terraform.py --test
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# Directory Paths
SCRIPT_DIR = Path(__file__).resolve().parent
TF_DIR = SCRIPT_DIR.parent
REPO_ROOT = TF_DIR.parent.parent

# Detect if running within a GitHub Actions CI environment
IS_CI = sys.platform != "win32" and os.environ.get("GITHUB_ACTIONS") == "true"

# ANSI Color Escape Codes
COLOR_GREEN = "\033[32m"
COLOR_RED = "\033[31m"
COLOR_RESET = "\033[0m"


def _colorize(text: str, color: str) -> str:
    """Wraps text in ANSI escape sequence if coloring is enabled."""
    if os.environ.get("NO_COLOR"):
        return text
    return f"{color}{text}{COLOR_RESET}"


def _status_passed() -> str:
    return _colorize("✓ Passed", COLOR_GREEN)


def _status_failed() -> str:
    return _colorize("✖ Failed", COLOR_RED)


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


def _display_cmd(cmd: list[str], tf_dir: Path) -> str:
    """Renders a command with paths relative to REPO_ROOT for clean readability."""
    prefix = f"{REPO_ROOT}/"
    tf_prefix = f"{tf_dir}/"
    tf_parent = f"{tf_dir.parent}/"
    rendered: list[str] = []
    for arg in cmd:
        clean = (
            arg.replace(f"-chdir={tf_prefix}", "-chdir=")
            .replace(f"-chdir={prefix}", "-chdir=")
            .replace(f"-chdir={tf_parent}", "-chdir=")
            .replace(prefix, "")
            .replace(tf_prefix, "")
            .replace(tf_parent, "")
            .replace(str(REPO_ROOT), "")
        )
        rendered.append(clean)
    return " ".join(rendered)


# ==============================================================================
# Header & UI Rendering Helpers
# ==============================================================================


def _print_phase_header(title: str, step: str = "") -> None:
    """Prints a distinct double-line framed header banner for a check phase."""
    divider = "─" * 70
    label = f"[{step}] {title}" if step else title
    print(f"{divider}\n {label}\n{divider}")


def _run_step(
    cmd: list[str],
    tf_dir: Path,
    chdir: Path | None = None,
    custom_failure_renderer: Callable[[str], None] | None = None,
    *,
    quiet_on_success: bool = False,
) -> tuple[bool, subprocess.CompletedProcess[str]]:
    """Prints command, executes it, and prints failure status + log on error.

    If quiet_on_success is True, the command is only displayed if it fails.
    Returns (success, result).
    """
    if not quiet_on_success:
        print(f"$ {_display_cmd(cmd, tf_dir)}")
    result = _run_cmd(cmd, chdir=chdir)
    if result.returncode != 0:
        if quiet_on_success:
            print(f"$ {_display_cmd(cmd, tf_dir)}")
        print(f"{_status_failed()}\n")
        if custom_failure_renderer:
            custom_failure_renderer(result.stdout)
        else:
            raw_output = result.stderr.strip() or result.stdout.strip()
            print(raw_output)
            print("")
        return False, result
    return True, result


def _extract_failing_files(output: str) -> list[str]:
    """Extracts unique source files mentioned in 'on <file> line <line>' error lines."""
    matches = re.findall(r"on\s+(\S+)\s+line\s+\d+", output)
    return sorted(set(matches))


def _extract_unformatted_files(stdout: str, tf_dir: Path) -> list[str]:
    """Parses terraform fmt stdout into relative paths from tf_dir."""
    unformatted: list[str] = []
    resolved_tf = tf_dir.resolve()
    resolved_repo = REPO_ROOT.resolve()
    for raw_line in stdout.strip().splitlines():
        path = Path(raw_line.strip()).resolve()
        try:
            rel = path.relative_to(resolved_tf)
        except ValueError:
            try:
                rel = path.relative_to(resolved_repo)
            except ValueError:
                rel = path
        unformatted.append(str(rel))
    return unformatted


def _extract_pass_count(test_output: str) -> str:
    """Extracts 'N passed' count from terraform test output."""
    match = re.search(r"(\d+ passed)", test_output)
    return match.group(1) if match else "passed"


def _format_target_label(target_dir: Path, tf_dir: Path) -> str:
    """Formats a human-readable relative label for a target directory."""
    if target_dir == tf_dir:
        return f"root ({tf_dir.name})"
    try:
        return str(target_dir.relative_to(tf_dir))
    except ValueError:
        return str(target_dir)


# ==============================================================================
# GitHub Actions CI Group & Annotation Helpers
# ==============================================================================


def _ci_group_start(title: str) -> None:
    if IS_CI:
        print(f"::group::{title}")


def _ci_group_end() -> None:
    if IS_CI:
        print("::endgroup::")


def _ci_error(title: str, message: str) -> None:
    if IS_CI:
        print(f"::error title={title}::{message}")


# ==============================================================================
# Test Suite Discovery Helper
# ==============================================================================


def _discover_test_suites(tf_dir: Path) -> list[tuple[Path, list[Path]]]:
    """Discovers all 'tests/' directories containing *.tftest.hcl files."""
    suites: list[tuple[Path, list[Path]]] = []
    test_dirs = sorted(
        p
        for p in tf_dir.rglob("tests")
        if p.is_dir()
        and ".terraform" not in p.parts
        and (tf_dir != TF_DIR or "scripts" not in p.parts)
    )
    for test_dir in test_dirs:
        test_files = sorted(test_dir.glob("*.tftest.hcl"))
        if test_files:
            suites.append((test_dir.parent, test_files))
    return suites


# ==============================================================================
# Structured Result Tracking & Final Summary
# ==============================================================================


@dataclass
class CheckSummary:
    """Collects failures across all executed checks."""

    unformatted_files: list[str] = field(default_factory=list)
    validation_failures: list[str] = field(default_factory=list)
    failed_test_targets: list[str] = field(default_factory=list)
    has_failure: bool = False

    def add_fmt_failure(self, files: list[str]) -> None:
        self.unformatted_files.extend(files)
        self.has_failure = True

    def add_validation_failure(self, files: list[str]) -> None:
        self.validation_failures.extend(files)
        self.has_failure = True

    def add_test_failure(self, target: str) -> None:
        self.failed_test_targets.append(target)
        self.has_failure = True


def _print_final_summary(summary: CheckSummary) -> None:
    """Prints a consolidated summary block at the bottom of the output."""
    divider = "─" * 70
    top_divider = "=" * 70

    if not summary.has_failure:
        print(f"{top_divider}\n Summary: {_status_passed()}\n{divider}\n")
        return

    print(f"{top_divider}\n Summary: {_status_failed()}\n{divider}")

    fail_icon = _colorize("✖", COLOR_RED)

    if summary.unformatted_files:
        count = len(summary.unformatted_files)
        file_plural = "file" if count == 1 else "files"
        print(f"\n  {fail_icon} Formatting ({count} {file_plural}):")
        for f in summary.unformatted_files:
            print(f"    - {f}")
        print("    ↳ Fix: uv run infra/dcp/scripts/check_terraform.py --fix")

    if summary.validation_failures:
        print(f"\n  {fail_icon} Terraform Validation:")
        for f in summary.validation_failures:
            print(f"    - {f}")

    if summary.failed_test_targets:
        count = len(summary.failed_test_targets)
        suite_plural = "suite" if count == 1 else "suites"
        print(f"\n  {fail_icon} Unit Tests ({count} {suite_plural} failed):")
        for t in summary.failed_test_targets:
            print(f"    - {t}")

    print(f"\n{divider}\n")


# ==============================================================================
# Public Check Operations: Format, Fix, Validate, Test
# ==============================================================================


def run_fmt(summary: CheckSummary, tf_dir: Path = TF_DIR, step: str = "1/3") -> None:
    """Checks Terraform formatting across tf_dir."""
    _print_phase_header("Formatting", step)
    cmd = ["terraform", "fmt", "-check", "-recursive", str(tf_dir)]

    def _render_fmt_failure(stdout: str) -> None:
        unformatted = _extract_unformatted_files(stdout, tf_dir)
        summary.add_fmt_failure(unformatted)
        print("Unformatted files:")
        for f in unformatted:
            print(f"  - {f}")
        print("")

    ok, _ = _run_step(cmd, tf_dir, custom_failure_renderer=_render_fmt_failure)
    if ok:
        print(f"{_status_passed()}\n")


def run_fix(tf_dir: Path = TF_DIR) -> bool:
    """Formats all Terraform files in tf_dir in-place."""
    _print_phase_header("Formatting In-Place")
    cmd = ["terraform", "fmt", "-recursive", str(tf_dir)]

    def _render_fix_failure(stdout: str) -> None:
        print(f"ERROR: Formatting failed:\n{stdout}")

    ok, _ = _run_step(cmd, tf_dir, custom_failure_renderer=_render_fix_failure)
    if ok:
        print(f"{_status_passed()}\n")
        return True
    return False


def run_validate(
    summary: CheckSummary, tf_dir: Path = TF_DIR, step: str = "2/3"
) -> None:
    """Initializes and validates Terraform configuration in tf_dir."""
    _print_phase_header("Validation", step)

    # 1. Initialize modules and providers quietly
    init_cmd = ["terraform", f"-chdir={tf_dir}", "init", "-backend=false"]
    ok, init_res = _run_step(init_cmd, tf_dir)
    if not ok:
        raw = init_res.stderr.strip() or init_res.stdout.strip()
        failing = _extract_failing_files(raw)
        summary.add_validation_failure(failing or [str(tf_dir)])
        return

    # 2. Validate configuration
    val_cmd = ["terraform", f"-chdir={tf_dir}", "validate"]
    ok, val_res = _run_step(val_cmd, tf_dir)
    if not ok:
        raw = val_res.stderr.strip() or val_res.stdout.strip()
        failing = _extract_failing_files(raw)
        summary.add_validation_failure(failing or [str(tf_dir)])
        return

    print(f"{_status_passed()}\n")


def run_tests(summary: CheckSummary, tf_dir: Path = TF_DIR, step: str = "3/3") -> None:
    """Discovers and executes all Terraform unit test suites across tf_dir."""
    _print_phase_header("Unit Tests", step)
    suites = _discover_test_suites(tf_dir)

    if not suites:
        print(f"{_status_passed()} (No tests found)\n")
        return

    for target_dir, test_files in suites:
        rel_target = _format_target_label(target_dir, tf_dir)
        _ci_group_start(f"[terraform test] {rel_target}")

        init_cmd = ["terraform", f"-chdir={target_dir}", "init", "-backend=false"]
        ok, _ = _run_step(init_cmd, tf_dir, quiet_on_success=True)
        if not ok:
            summary.add_test_failure(rel_target)
            _ci_group_end()
            continue

        test_cmd = ["terraform", f"-chdir={target_dir}", "test"]
        ok, test_res = _run_step(test_cmd, tf_dir)
        if not ok:
            summary.add_test_failure(rel_target)
            _ci_error("Terraform Test Failure", f"Tests failed in {rel_target}")
        else:
            pass_count = _extract_pass_count(test_res.stdout)
            for tf_file in test_files:
                print(f"  - {tf_file.name} ({pass_count})")
            print(f"{_status_passed()}\n")

        _ci_group_end()


# ==============================================================================
# CLI Entrypoint & Argument Parsing
# ==============================================================================


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Lint, validate, and test DCP Terraform configurations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--fmt",
        action="store_true",
        help="Check Terraform formatting across infra/dcp (read-only).",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply Terraform formatting in-place across infra/dcp (mutates files).",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate Terraform configuration (read-only).",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Discover and execute all *.tftest.hcl unit test suites (read-only).",
    )
    parser.add_argument(
        "--tf-dir",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,  # Hidden internal parameter for unit testing
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, tf_dir: Path | None = None) -> int:
    """Main CLI dispatch entrypoint."""
    args = parse_args(argv)
    target_tf_dir = tf_dir or args.tf_dir or TF_DIR

    if args.fix:
        return 0 if run_fix(target_tf_dir) else 1

    summary = CheckSummary()

    if args.fmt:
        run_fmt(summary, target_tf_dir, step="")
    elif args.validate:
        run_validate(summary, target_tf_dir, step="")
    elif args.test:
        run_tests(summary, target_tf_dir, step="")
    else:
        # Default: execute all three verification checks sequentially
        run_fmt(summary, target_tf_dir, step="1/3")
        run_validate(summary, target_tf_dir, step="2/3")
        run_tests(summary, target_tf_dir, step="3/3")

    _print_final_summary(summary)
    return 1 if summary.has_failure else 0


if __name__ == "__main__":
    sys.exit(main())
