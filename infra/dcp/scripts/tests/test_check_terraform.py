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

"""Tests for infra/dcp/scripts/check_terraform.py.

These hermetic tests use minimal, cloud-free Terraform fixtures to verify
core functional behavior across formatting, validation, and unit tests.
Developers can run any scenario with `uv run pytest -s -k <scenario>` to
visually inspect the CLI output.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest
from check_terraform import _discover_test_suites, main

FIXTURE_BASELINE_DIR = Path(__file__).resolve().parent / "fixtures" / "baseline"


def strip_ansi(text: str) -> str:
    """Strips ANSI color codes from terminal output for assertions."""
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

SYNTAX_ERROR_HCL = """locals {
  message = "unterminated
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
def tf_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copies baseline fixture into a temporary test directory."""
    env_dir = tmp_path / "tf_project"
    shutil.copytree(FIXTURE_BASELINE_DIR, env_dir)
    monkeypatch.chdir(tmp_path)
    return env_dir


def _run_and_capture(
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    tf_dir: Path,
) -> tuple[int, str]:
    """Executes main() and captures stdout, re-emitting so pytest -s prints output."""
    exit_code = main(["--tf-dir", str(tf_dir), *argv])
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
    """All phases pass across 2 unit test modules -> exits 0."""
    _create_test_module(tf_env, "module_a")
    _create_test_module(tf_env, "module_b")

    exit_code, out = _run_and_capture(capsys, [], tf_env)

    assert exit_code == 0
    assert "Summary: ✓ Passed" in out


def test_fmt_fails(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Formatting check fails -> exits 1, reports unformatted file and --fix hint."""
    (tf_env / "main.tf").write_text(BAD_FORMAT_HCL)

    exit_code, out = _run_and_capture(capsys, ["--fmt"], tf_env)

    assert exit_code == 1
    assert "main.tf" in out
    assert "--fix" in out


def test_fix_reformats_files(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--fix reformats unformatted files in-place so subsequent --fmt passes."""
    (tf_env / "main.tf").write_text(BAD_FORMAT_HCL)

    fix_code, fix_out = _run_and_capture(capsys, ["--fix"], tf_env)
    assert fix_code == 0
    assert "│ main.tf" in fix_out

    fmt_code, _ = _run_and_capture(capsys, ["--fmt"], tf_env)
    assert fmt_code == 0


def test_fmt_syntax_error(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--fmt on an HCL syntax error exits 1 and forwards Terraform's stderr diagnostic."""
    (tf_env / "main.tf").write_text(SYNTAX_ERROR_HCL)

    exit_code, out = _run_and_capture(capsys, ["--fmt"], tf_env)

    assert exit_code == 1
    assert "main.tf" in out
    assert "Error:" in out


def test_validate_init_fails(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """terraform init failure during --validate exits 1 and forwards diagnostic."""
    (tf_env / "main.tf").write_text(INVALID_INIT_HCL)

    exit_code, out = _run_and_capture(capsys, ["--validate"], tf_env)

    assert exit_code == 1
    assert "Unsupported Terraform Core version" in out


def test_validate_cmd_fails(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """terraform validate failure exits 1 and reports the failing file and reason."""
    (tf_env / "main.tf").write_text(INVALID_VALIDATION_HCL)

    exit_code, out = _run_and_capture(capsys, ["--validate"], tf_env)

    assert exit_code == 1
    assert "Invalid operand" in out
    assert "main.tf" in out


def test_unit_test_fails_mixed(
    tf_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Mixed module results -> exits 1, reports failing module_b without blaming module_a."""
    _create_test_module(tf_env, "module_a", fails=False)
    _create_test_module(
        tf_env, "module_b", fails=True, error_message="module_b assertion failed"
    )

    exit_code, out = _run_and_capture(capsys, ["--test"], tf_env)

    assert exit_code == 1
    assert "module_b assertion failed" in out
    assert "- modules/module_b" in out
    assert "- modules/module_a" not in out


def test_no_suites_found_fails(
    tf_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--test exits 1 when zero *.tftest.hcl suites exist."""
    exit_code, out = _run_and_capture(capsys, ["--test"], tf_env)

    assert exit_code == 1
    assert "No *.tftest.hcl test suites found" in out


def test_all_fail(tf_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Compound failure runs all 3 phases without short-circuiting and aggregates culprits."""
    (tf_env / "main.tf").write_text(BAD_FORMAT_HCL + "\n" + INVALID_VALIDATION_HCL)
    _create_test_module(
        tf_env, "module_a", fails=True, error_message="module_a assertion failed"
    )
    _create_test_module(
        tf_env, "module_b", fails=True, error_message="module_b assertion failed"
    )

    exit_code, out = _run_and_capture(capsys, [], tf_env)

    assert exit_code == 1
    assert "- main.tf" in out
    assert "module_a assertion failed" in out
    assert "module_b assertion failed" in out
    assert "- modules/module_a" in out
    assert "- modules/module_b" in out


def test_discover_test_suites(tf_env: Path) -> None:
    """_discover_test_suites finds module suites and ignores .terraform/ directories."""
    mod_a = _create_test_module(tf_env, "module_a")
    cached_tests = tf_env / ".terraform" / "modules" / "cached" / "tests"
    cached_tests.mkdir(parents=True)
    (cached_tests / "ignored.tftest.hcl").write_text("# cached\n")

    suites = _discover_test_suites(tf_env)

    assert suites == [mod_a]
