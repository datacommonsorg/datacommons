"""Tests for infra/dcp/scripts/check_terraform.py.

These hermetic unit tests use minimal, cloud-free Terraform fixtures to test all
pass and fail scenarios across formatting, validation, and unit tests.
Developers can run any test scenario with `pytest -s -k <scenario>` to visually
inspect the exact CLI output formatting.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest
from check_terraform import main

FIXTURE_BASELINE_DIR = Path(__file__).resolve().parent / "fixtures" / "baseline"


def strip_ansi(text: str) -> str:
    """Strips ANSI color codes from terminal output for robust assertions."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


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

INVALID_INIT_HCL = """terraform {
  required_version = "= 0.0.1"
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
    sys.stdout.write(f"\n{captured.out}")
    return exit_code, strip_ansi(captured.out)


def _create_test_module(
    tf_env: Path,
    name: str,
    *,
    fails: bool = False,
    error_message: str = "assertion failed",
) -> Path:
    """Creates a hermetic submodule with a tftest.hcl test suite."""
    mod_dir = tf_env / "modules" / name
    mod_tests = mod_dir / "tests"
    mod_tests.mkdir(parents=True, exist_ok=True)
    expected_value = f"{name}-expected"
    actual_value = f"{name}-typo" if fails else expected_value

    (mod_dir / "main.tf").write_text(f"""terraform {{
  required_version = ">= 1.5.0"
}}

locals {{
  name = "{actual_value}"
}}
""")
    (mod_tests / "unit.tftest.hcl").write_text(f"""run "verify" {{
  command = plan
  assert {{
    condition     = local.name == "{expected_value}"
    error_message = "{error_message}"
  }}
}}
""")
    return mod_dir


def test_all_pass(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 1: Formatting OK, validate OK, 2 unit test modules pass -> Summary: ✓ Passed."""
    shutil.rmtree(tf_env / "tests")
    _create_test_module(tf_env, "module_a")
    _create_test_module(tf_env, "module_b")

    exit_code, out = _run_and_capture(capsys, [], tf_env)

    assert exit_code == 0
    assert "[1/3] Formatting" in out
    assert "$ terraform fmt -check -recursive" in out
    assert "[2/3] Validation" in out
    assert "$ terraform -chdir=tf_project init -backend=false" in out
    assert "$ terraform -chdir=tf_project validate" in out
    assert "[3/3] Unit Tests" in out
    assert "$ terraform -chdir=modules/module_a test" in out
    assert "$ terraform -chdir=modules/module_b test" in out
    assert "  - unit.tftest.hcl (1 passed)" in out
    assert "✓ Passed" in out
    assert "Summary: ✓ Passed" in out
    assert "Summary: ✖ Failed" not in out


def test_fmt_fails(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 2: Formatting failure with --fmt -> exit 1, lists files, suggests --fix."""
    (tf_env / "main.tf").write_text(BAD_FORMAT_HCL)

    exit_code, out = _run_and_capture(capsys, ["--fmt"], tf_env)

    assert exit_code == 1
    assert "Formatting" in out
    assert "[1/3]" not in out
    assert "Validation" not in out
    assert "Unit Tests" not in out
    assert "$ terraform fmt -check -recursive" in out
    assert "✖ Failed" in out
    assert "Unformatted files:\n  - main.tf" in out
    assert "✖ Formatting (1 file):" in out
    assert "↳ Fix: uv run infra/dcp/scripts/check_terraform.py --fix" in out
    assert "Summary: ✖ Failed" in out


def test_validate_init_fails(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 3: terraform init failure with --validate -> logs init command, exits 1."""
    (tf_env / "main.tf").write_text(INVALID_INIT_HCL)

    exit_code, out = _run_and_capture(capsys, ["--validate"], tf_env)

    assert exit_code == 1
    assert "Validation" in out
    assert "[2/3]" not in out
    assert "Formatting" not in out
    assert "Unit Tests" not in out
    assert "$ terraform -chdir=tf_project init -backend=false" in out
    assert "✖ Failed" in out
    assert "Failure log:" not in out
    assert "Unsupported Terraform Core version" in out
    assert "✖ Terraform Validation:" in out
    assert "Summary: ✖ Failed" in out


def test_validate_cmd_fails(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 4: terraform validate failure with --validate -> logs validate command, exits 1."""
    (tf_env / "main.tf").write_text(INVALID_VALIDATION_HCL)

    exit_code, out = _run_and_capture(capsys, ["--validate"], tf_env)

    assert exit_code == 1
    assert "Validation" in out
    assert "[2/3]" not in out
    assert "Formatting" not in out
    assert "Unit Tests" not in out
    assert "$ terraform -chdir=tf_project init -backend=false" in out
    assert "$ terraform -chdir=tf_project validate" in out
    assert "✖ Failed" in out
    assert "Failure log:" not in out
    assert "Invalid operand" in out
    assert "main.tf" in out
    assert "✖ Terraform Validation:" in out
    assert "Summary: ✖ Failed" in out


def test_unit_test_fails_mixed(
    tf_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario 5: Multiple modules with --test -> module_a passes, module_b fails."""
    shutil.rmtree(tf_env / "tests")
    _create_test_module(tf_env, "module_a", fails=False)
    _create_test_module(
        tf_env, "module_b", fails=True, error_message="module_b assertion failed"
    )

    exit_code, out = _run_and_capture(capsys, ["--test"], tf_env)

    assert exit_code == 1
    assert "Unit Tests" in out
    assert "[3/3]" not in out
    assert "Formatting" not in out
    assert "Validation" not in out
    # module_a passes
    assert (
        "$ terraform -chdir=modules/module_a test\n"
        "  - unit.tftest.hcl (1 passed)\n"
        "✓ Passed"
    ) in out
    # module_b fails
    assert "$ terraform -chdir=modules/module_b test\n✖ Failed" in out
    assert "module_b assertion failed" in out
    assert "Failure log:" not in out
    # Summary lists ONLY module_b
    assert "✖ Unit Tests (1 suite failed):" in out
    assert "- modules/module_b" in out
    assert "- modules/module_a" not in out
    assert "Action: Inspect" not in out
    assert "Summary: ✖ Failed" in out


def test_all_fail(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario 6: Total failure -> formatting fails, validation fails, both modules fail."""
    bad_all_hcl = """terraform {
required_version = ">= 1.5.0"
}

locals {
message = 1 + "invalid"
}
"""
    (tf_env / "main.tf").write_text(bad_all_hcl)

    # Submodule test setup: both module_a and module_b fail
    shutil.rmtree(tf_env / "tests")
    _create_test_module(
        tf_env, "module_a", fails=True, error_message="module_a assertion failed"
    )
    _create_test_module(
        tf_env, "module_b", fails=True, error_message="module_b assertion failed"
    )

    exit_code, out = _run_and_capture(capsys, [], tf_env)

    assert exit_code == 1
    # All three phases ran
    assert "[1/3] Formatting" in out
    assert "[2/3] Validation" in out
    assert "[3/3] Unit Tests" in out

    # Unit tests: both fail
    assert "$ terraform -chdir=modules/module_a test" in out
    assert "module_a assertion failed" in out
    assert "$ terraform -chdir=modules/module_b test" in out
    assert "module_b assertion failed" in out
    assert out.count("✖ Failed") == 5

    # Summary contains all 3 failure sections with 2 test suites failed
    assert "✖ Formatting (1 file):" in out
    assert "↳ Fix: uv run infra/dcp/scripts/check_terraform.py --fix" in out
    assert "✖ Terraform Validation:" in out
    assert "✖ Unit Tests (2 suites failed):" in out
    assert "- modules/module_a" in out
    assert "- modules/module_b" in out
    assert "Action: Inspect" not in out
    assert "Summary: ✖ Failed" in out
