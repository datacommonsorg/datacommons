"""Tests for infra/dcp/scripts/check_terraform.py.

These hermetic unit tests use minimal, cloud-free Terraform fixtures to test all
pass and fail scenarios across formatting, validation, and unit tests.
Developers can run any test scenario with `pytest -s -k <scenario>` to visually
inspect the exact CLI output formatting.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from check_terraform import main

FIXTURE_BASELINE_DIR = Path(__file__).resolve().parent / "fixtures" / "baseline"

BAD_FORMAT_HCL = """terraform {
required_version = ">= 1.5.0"
}

variable "status" {
      type = string
  default = "active"
}

locals {
message = "hello-${var.status}"
}
"""

INVALID_VALIDATION_HCL = """terraform {
  required_version = ">= 1.5.0"
}

variable "status" {
  type    = string
  default = "active"
}

locals {
  message = 1 + "invalid"
}
"""

FAILING_TEST_HCL = """run "verify_message" {
  command = plan
  assert {
    condition     = local.message == "wrong-value"
    error_message = "unexpected message value"
  }
}
"""


@pytest.fixture
def tf_env(tmp_path: Path) -> Path:
    """Copies baseline fixture into a temporary test directory."""
    env_dir = tmp_path / "tf_project"
    shutil.copytree(FIXTURE_BASELINE_DIR, env_dir)
    return env_dir


def _run_and_capture(
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    tf_dir: Path,
) -> tuple[int, str]:
    """Executes main() and captures stdout, re-emitting so pytest -s prints output."""
    exit_code = main(argv, tf_dir=tf_dir)
    captured = capsys.readouterr()
    sys.stdout.write(captured.out)
    return exit_code, captured.out


def test_all_pass(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 1: Formatting OK, validate OK, unit tests OK -> SUMMARY: ALL PASSED."""
    exit_code, out = _run_and_capture(capsys, [], tf_env)

    assert exit_code == 0
    assert "==> Checking formatting..." in out
    assert "==> Validating Terraform..." in out
    assert "==> Running unit tests..." in out
    assert "status: OK" in out
    assert "SUMMARY: ALL PASSED" in out
    assert "SUMMARY: CHECKS FAILED" not in out


def test_format_failure(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 2: Formatting failure -> exit 1, lists files, suggests --fix."""
    (tf_env / "main.tf").write_text(BAD_FORMAT_HCL)

    exit_code, out = _run_and_capture(capsys, [], tf_env)

    assert exit_code == 1
    assert "==> Checking formatting..." in out
    assert "status: FAILED" in out
    assert "Failing file(s):" in out
    assert "main.tf" in out
    assert "[FAILED] Formatting (1 file needs formatting):" in out
    assert "Action: Run 'uv run infra/dcp/scripts/check_terraform.py --fix'" in out
    assert "SUMMARY: CHECKS FAILED" in out


def test_validation_failure(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 3: Validation failure -> exit 1, frames raw error log, lists files."""
    (tf_env / "main.tf").write_text(INVALID_VALIDATION_HCL)

    exit_code, out = _run_and_capture(capsys, [], tf_env)

    assert exit_code == 1
    assert "==> Validating Terraform..." in out
    assert "status: FAILED" in out
    assert "--- Terraform Output ---" in out
    assert "------------------------" in out
    assert "main.tf" in out
    assert "[FAILED] Terraform Validation:" in out
    assert "SUMMARY: CHECKS FAILED" in out


def test_unit_test_failure(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 4: Test assertion failure -> exit 1, frames test failure, lists target."""
    (tf_env / "tests" / "unit.tftest.hcl").write_text(FAILING_TEST_HCL)

    exit_code, out = _run_and_capture(capsys, [], tf_env)

    assert exit_code == 1
    assert "==> Running unit tests..." in out
    assert "status: FAILED" in out
    assert "--- Terraform Output ---" in out
    assert "------------------------" in out
    assert "[FAILED] Unit Tests (1 suite failed):" in out
    assert (
        "Action: Inspect failure logs above or run 'uv run infra/dcp/scripts/check_terraform.py --test'"
        in out
    )
    assert "SUMMARY: CHECKS FAILED" in out


def test_format_and_validation_failure(
    tf_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario 5: Format and validate both fail -> exit 1, both in summary."""
    bad_fmt_and_val = """terraform {
required_version = ">= 1.5.0"
}

locals {
message = 1 + "invalid"
}
"""
    (tf_env / "main.tf").write_text(bad_fmt_and_val)

    exit_code, out = _run_and_capture(capsys, [], tf_env)

    assert exit_code == 1
    assert "[FAILED] Formatting (1 file needs formatting):" in out
    assert "[FAILED] Terraform Validation:" in out
    assert "SUMMARY: CHECKS FAILED" in out


def test_all_three_failure(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 6: Format, validate, and tests all fail -> exit 1, all 3 in summary."""
    bad_fmt_and_val = """terraform {
required_version = ">= 1.5.0"
}

locals {
message = 1 + "invalid"
}
"""
    (tf_env / "main.tf").write_text(bad_fmt_and_val)
    (tf_env / "tests" / "unit.tftest.hcl").write_text(FAILING_TEST_HCL)

    exit_code, out = _run_and_capture(capsys, [], tf_env)

    assert exit_code == 1
    assert "[FAILED] Formatting (1 file needs formatting):" in out
    assert "[FAILED] Terraform Validation:" in out
    assert "[FAILED] Unit Tests (1 suite failed):" in out
    assert "SUMMARY: CHECKS FAILED" in out


def test_fix_flag(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 7: --fix formats files in-place and subsequent check passes."""
    (tf_env / "main.tf").write_text(BAD_FORMAT_HCL)

    # 1. Run with --fix
    exit_code, out = _run_and_capture(capsys, ["--fix"], tf_env)
    assert exit_code == 0
    assert "==> Formatting files in place..." in out
    assert "status: OK" in out

    # 2. Run with --fmt to verify it's now formatted
    exit_code_fmt, out_fmt = _run_and_capture(capsys, ["--fmt"], tf_env)
    assert exit_code_fmt == 0
    assert "status: OK" in out_fmt
    assert "SUMMARY: ALL PASSED" in out_fmt


def test_single_flag_fmt(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 8: --fmt runs only formatting check."""
    (tf_env / "main.tf").write_text(BAD_FORMAT_HCL)

    exit_code, out = _run_and_capture(capsys, ["--fmt"], tf_env)

    assert exit_code == 1
    assert "==> Checking formatting..." in out
    assert "==> Validating Terraform..." not in out
    assert "==> Running unit tests..." not in out
    assert "[FAILED] Formatting (1 file needs formatting):" in out
    assert "SUMMARY: CHECKS FAILED" in out


def test_single_flag_validate(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 9: --validate runs only validation check."""
    # Indentation is unformatted, but validation is clean
    (tf_env / "main.tf").write_text(BAD_FORMAT_HCL)

    exit_code, out = _run_and_capture(capsys, ["--validate"], tf_env)

    assert exit_code == 0
    assert "==> Checking formatting..." not in out
    assert "==> Validating Terraform..." in out
    assert "status: OK" in out
    assert "==> Running unit tests..." not in out
    assert "SUMMARY: ALL PASSED" in out


def test_single_flag_test(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 10: --test runs only unit test suite."""
    # Indentation is unformatted, but syntax and tests are clean
    (tf_env / "main.tf").write_text(BAD_FORMAT_HCL)

    exit_code, out = _run_and_capture(capsys, ["--test"], tf_env)

    assert exit_code == 0
    assert "==> Checking formatting..." not in out
    assert "==> Validating Terraform..." not in out
    assert "==> Running unit tests..." in out
    assert "status: OK" in out
    assert "unit.tftest.hcl (1 passed)" in out
    assert "SUMMARY: ALL PASSED" in out
