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

"""Unit tests for CI/CD deployment and release automation scripts.

Tests cover:
  1. apply_version_bump.py - Single source of truth version bumper.
  2. validate_release_version.py - Pre-publish version consistency validator.
  3. publish_packages.py - Package builder and PyPI / TestPyPI distributor.
  4. tag_release_artifacts.py - Multi-artifact release tagger and template stager.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import apply_version_bump as bumper
import publish_packages as publisher
import pytest
import tag_release_artifacts as tagger
import validate_release_version as validator

# ==============================================================================
# Fixtures & Test Environment Setup
# ==============================================================================


@pytest.fixture
def mock_monorepo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Constructs a minimal, hermetic mock monorepo tree for testing."""
    # 1. Root VERSION
    (tmp_path / "VERSION").write_text("1.0.0\n")

    # 2. Terraform variables.tf
    tf_dir = tmp_path / "infra" / "dcp"
    tf_dir.mkdir(parents=True)
    (tf_dir / "variables.tf").write_text(
        'variable "project_id" {\n'
        "  type = string\n"
        "}\n\n"
        'variable "dcp_version" {\n'
        '  description = "The version of the Data Commons Platform"\n'
        "  type        = string\n"
        '  default     = "1.0.0"\n'
        "}\n"
    )

    # 3. Subpackages
    pkgs_dir = tmp_path / "packages"
    pkgs_dir.mkdir()

    # datacommons-db
    db_dir = pkgs_dir / "datacommons-db"
    db_dir.mkdir()
    (db_dir / "pyproject.toml").write_text(
        '[project]\nname = "datacommons-db"\nversion = "1.0.0"\n'
    )
    (db_dir / "VERSION").write_text("1.0.0\n")

    # datacommons-admin
    admin_dir = pkgs_dir / "datacommons-admin"
    admin_dir.mkdir()
    (admin_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "datacommons-admin"\n'
        "dependencies = [\n"
        '  "datacommons-db==1.0.0",\n'
        "]\n"
    )
    (admin_dir / "VERSION").write_text("1.0.0\n")

    # datacommons-cli
    cli_dir = pkgs_dir / "datacommons-cli"
    cli_dir.mkdir()
    (cli_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "datacommons-cli"\n'
        "dependencies = [\n"
        '  "click>=8.1.7",\n'
        '  "datacommons-admin==1.0.0",\n'
        "]\n"
    )
    (cli_dir / "VERSION").write_text("1.0.0\n")

    # Non-package auxiliary directory (should be ignored)
    (pkgs_dir / ".DS_Store").touch()

    # Monkeypatch REPO_ROOT across all three modules
    monkeypatch.setattr(bumper, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(publisher, "REPO_ROOT", tmp_path)

    return tmp_path


# ==============================================================================
# Suite 1: apply_version_bump.py
# ==============================================================================


class TestApplyVersionBump:
    @pytest.mark.parametrize(
        ("input_version", "expected_version"),
        [
            ("1.2.3", "1.2.3"),
            ("v1.2.3", "1.2.3"),
            ("  v2.0.0rc1  \n", "2.0.0rc1"),
            ("1.2.0.dev0", "1.2.0.dev0"),
        ],
    )
    def test_apply_version_bump_updates_all_manifests(
        self, mock_monorepo: Path, input_version: str, expected_version: str
    ) -> None:
        """// Test: test_apply_version_bump_updates_all_manifests

        // Situation: apply_version_bump is called with various SemVer/PEP 440
        formats.
        // Expectation: Root VERSION, subpackage VERSIONs, variables.tf, and
        pyproject.toml are updated cleanly.
        """
        bumper.apply_version_bump(input_version)

        # 1. Root VERSION
        assert (mock_monorepo / "VERSION").read_text().strip() == expected_version

        # 2. Subpackage VERSION files
        assert (
            mock_monorepo / "packages/datacommons-db/VERSION"
        ).read_text().strip() == expected_version
        assert (
            mock_monorepo / "packages/datacommons-admin/VERSION"
        ).read_text().strip() == expected_version
        assert (
            mock_monorepo / "packages/datacommons-cli/VERSION"
        ).read_text().strip() == expected_version

        # 3. Terraform variables.tf
        tf_content = (mock_monorepo / "infra/dcp/variables.tf").read_text()
        assert f'default     = "{expected_version}"' in tf_content

        # 4. Lockstep subpackage dependencies
        admin_toml = (
            mock_monorepo / "packages/datacommons-admin/pyproject.toml"
        ).read_text()
        assert f'"datacommons-db=={expected_version}"' in admin_toml

        cli_toml = (
            mock_monorepo / "packages/datacommons-cli/pyproject.toml"
        ).read_text()
        assert f'"datacommons-admin=={expected_version}"' in cli_toml

    @pytest.mark.parametrize("invalid_version", ["", "v", "   \n  "])
    def test_apply_version_bump_rejects_empty_version(
        self, mock_monorepo: Path, invalid_version: str
    ) -> None:
        """// Test: test_apply_version_bump_rejects_empty_version

        // Situation: apply_version_bump is called with an empty or whitespace
        version string.
        // Expectation: Script calls sys.exit with an error message.
        """
        with pytest.raises(SystemExit) as exc_info:
            bumper.apply_version_bump(invalid_version)
        assert "Target version cannot be empty" in str(exc_info.value)

    @pytest.mark.parametrize(
        "malformed_version",
        ["foo", "1.2", "1.2.3.4.5", "release-1.2.3", "v-latest", "1.2.3-beta"],
    )
    def test_apply_version_bump_rejects_malformed_version_pattern(
        self, mock_monorepo: Path, malformed_version: str
    ) -> None:
        """// Test: test_apply_version_bump_rejects_malformed_version_pattern

        // Situation: apply_version_bump is called with a non-SemVer/PEP 440 string.
        // Expectation: Script calls sys.exit rejecting invalid version format.
        """
        with pytest.raises(SystemExit) as exc_info:
            bumper.apply_version_bump(malformed_version)
        assert "Invalid version format" in str(exc_info.value)

    def test_apply_version_bump_missing_tf_variable_aborts(
        self, mock_monorepo: Path
    ) -> None:
        """// Test: test_apply_version_bump_missing_tf_variable_aborts

        // Situation: variables.tf exists but does not declare dcp_version.
        // Expectation: Script calls sys.exit with specific error message.
        """
        (mock_monorepo / "infra/dcp/variables.tf").write_text('variable "other" {}')
        with pytest.raises(SystemExit) as exc_info:
            bumper.apply_version_bump("1.2.3")
        assert "variable 'dcp_version' default not found" in str(exc_info.value)

    def test_apply_version_bump_missing_admin_dep_aborts(
        self, mock_monorepo: Path
    ) -> None:
        """// Test: test_apply_version_bump_missing_admin_dep_aborts

        // Situation: datacommons-cli pyproject.toml is missing datacommons-admin
        dependency.
        // Expectation: Script calls sys.exit with specific error message.
        """
        (mock_monorepo / "packages/datacommons-cli/pyproject.toml").write_text(
            '[project]\nname = "datacommons-cli"\ndependencies = ["click"]\n'
        )
        with pytest.raises(SystemExit) as exc_info:
            bumper.apply_version_bump("1.2.3")
        assert "datacommons-admin dependency not found" in str(exc_info.value)

    def test_apply_version_bump_missing_db_dep_aborts(
        self, mock_monorepo: Path
    ) -> None:
        """// Test: test_apply_version_bump_missing_db_dep_aborts

        // Situation: datacommons-admin pyproject.toml is missing datacommons-db
        dependency.
        // Expectation: Script calls sys.exit with specific error message.
        """
        (mock_monorepo / "packages/datacommons-admin/pyproject.toml").write_text(
            '[project]\nname = "datacommons-admin"\ndependencies = ["click"]\n'
        )
        with pytest.raises(SystemExit) as exc_info:
            bumper.apply_version_bump("1.2.3")
        assert "datacommons-db dependency not found" in str(exc_info.value)


# ==============================================================================
# Suite 2: validate_release_version.py
# ==============================================================================


class TestValidateReleaseVersion:
    @pytest.mark.parametrize("target_version", ["1.0.0", "v1.0.0"])
    def test_validate_release_version_success(
        self, mock_monorepo: Path, target_version: str
    ) -> None:
        """// Test: test_validate_release_version_success

        // Situation: All manifests cleanly declare 1.0.0.
        // Expectation: validate_release_version completes successfully without
        raising SystemExit.
        """
        validator.validate_release_version(target_version)

    @pytest.mark.parametrize(
        "malformed_version",
        ["foo", "1.2", "1.2.3.4.5", "release-1.2.3", "v-latest", ""],
    )
    def test_validate_release_version_rejects_malformed_version_pattern(
        self, mock_monorepo: Path, malformed_version: str
    ) -> None:
        """// Test: test_validate_release_version_rejects_malformed_version_pattern

        // Situation: validate_release_version is called with an invalid/malformed version tag.
        // Expectation: Script calls sys.exit rejecting invalid version tag.
        """
        with pytest.raises(SystemExit) as exc_info:
            validator.validate_release_version(malformed_version)
        assert "Invalid release tag/version format" in str(
            exc_info.value
        ) or "Target version cannot be empty" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("manifest_path", "mismatched_dep"),
        [
            ("packages/datacommons-cli/pyproject.toml", '"datacommons-admin==1.0.00"'),
            (
                "packages/datacommons-cli/pyproject.toml",
                '"datacommons-admin==1.0.0rc1"',
            ),
            ("packages/datacommons-cli/pyproject.toml", '"datacommons-admin>=1.0.0"'),
            ("packages/datacommons-cli/pyproject.toml", '"datacommons-admin~=1.0.0"'),
            ("packages/datacommons-cli/pyproject.toml", '"datacommons-admin"'),
            ("packages/datacommons-admin/pyproject.toml", '"datacommons-db==1.0.00"'),
            ("packages/datacommons-admin/pyproject.toml", '"datacommons-db==1.0.0rc1"'),
            ("packages/datacommons-admin/pyproject.toml", '"datacommons-db>=1.0.0"'),
            ("packages/datacommons-admin/pyproject.toml", '"datacommons-db~=1.0.0"'),
            ("packages/datacommons-admin/pyproject.toml", '"datacommons-db"'),
        ],
    )
    def test_validate_release_version_catches_dependency_mismatches(
        self, mock_monorepo: Path, manifest_path: str, mismatched_dep: str
    ) -> None:
        """// Test: test_validate_release_version_catches_dependency_mismatches

        // Situation: Subpackage pyproject.toml locks a loose or mismatched version.
        // Expectation: validate_release_version aborts with exit code 1.
        """
        pkg_name = Path(manifest_path).parent.name
        (mock_monorepo / manifest_path).write_text(
            f'[project]\nname = "{pkg_name}"\ndependencies = [{mismatched_dep}]\n'
        )
        with pytest.raises(SystemExit) as exc_info:
            validator.validate_release_version("1.0.0")
        assert exc_info.value.code == 1

    def test_validate_release_version_aggregates_multiple_errors(
        self, mock_monorepo: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """// Test: test_validate_release_version_aggregates_multiple_errors

        // Situation: Root VERSION, variables.tf, and cli pyproject.toml are
        simultaneously mismatched.
        // Expectation: Output lists all three distinct validation errors before
        exiting.
        """
        (mock_monorepo / "VERSION").write_text("0.9.0\n")
        (mock_monorepo / "infra/dcp/variables.tf").write_text(
            'variable "dcp_version" { default = "0.8.0" }'
        )
        (mock_monorepo / "packages/datacommons-cli/pyproject.toml").write_text(
            '[project]\ndependencies = ["datacommons-admin==0.7.0"]\n'
        )

        with pytest.raises(SystemExit) as exc_info:
            validator.validate_release_version("1.0.0")

        assert exc_info.value.code == 1
        captured = capsys.readouterr().out
        assert "Root VERSION file (0.9.0) does not match target" in captured
        assert "dcp_version default (0.8.0) does not match target" in captured
        assert (
            "locks datacommons-admin to '0.7.0' instead of target '1.0.0'" in captured
        )

    def test_validate_release_version_missing_files_fails(
        self, mock_monorepo: Path
    ) -> None:
        """// Test: test_validate_release_version_missing_files_fails

        // Situation: Root VERSION file is deleted.
        // Expectation: Validator reports missing file and exits with 1.
        """
        (mock_monorepo / "VERSION").unlink()
        with pytest.raises(SystemExit) as exc_info:
            validator.validate_release_version("1.0.0")
        assert exc_info.value.code == 1

    def test_validate_release_version_remote_artifacts_success(
        self, mock_monorepo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_validate_release_version_remote_artifacts_success

        // Situation: validate_release_version is called with --check-remote-artifacts
        and all images and templates exist.
        // Expectation: Validator passes cleanly without error.
        """
        monkeypatch.setattr(
            subprocess, "run", lambda *args, **kwargs: MagicMock(returncode=0)
        )
        validator.validate_release_version("1.0.0", check_remote_artifacts=True)

    def test_validate_release_version_remote_image_missing_fails(
        self, mock_monorepo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_validate_release_version_remote_image_missing_fails

        // Situation: validate_release_version is called with --check-remote-artifacts
        and a container image does not exist in registry.
        // Expectation: Validator aborts with exit code 1.
        """

        def mock_run(cmd, **kwargs):
            if ("container" in cmd and "images" in cmd) or (
                "artifacts" in cmd and "docker" in cmd
            ):
                return MagicMock(returncode=1)
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        with pytest.raises(SystemExit) as exc_info:
            validator.validate_release_version("1.0.0", check_remote_artifacts=True)
        assert exc_info.value.code == 1

    def test_validate_release_version_remote_template_missing_fails(
        self, mock_monorepo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_validate_release_version_remote_template_missing_fails

        // Situation: validate_release_version is called with --check-remote-artifacts
        and the GCS template spec is missing.
        // Expectation: Validator aborts with exit code 1.
        """

        def mock_run(cmd, **kwargs):
            if "storage" in cmd and "ls" in cmd:
                return MagicMock(returncode=1)
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        with pytest.raises(SystemExit) as exc_info:
            validator.validate_release_version("1.0.0", check_remote_artifacts=True)
        assert exc_info.value.code == 1

    def test_validate_release_version_missing_gcloud_fails(
        self, mock_monorepo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_validate_release_version_missing_gcloud_fails

        // Situation: check_remote_artifacts is True but gcloud is not installed.
        // Expectation: Validator reports missing gcloud and exits with 1.
        """
        monkeypatch.setattr(
            shutil,
            "which",
            lambda cmd: None if cmd == "gcloud" else "/usr/bin/" + cmd,
        )
        with pytest.raises(SystemExit) as exc_info:
            validator.validate_release_version("1.0.0", check_remote_artifacts=True)
        assert exc_info.value.code == 1


# ==============================================================================
# Suite 3: publish_packages.py
# ==============================================================================


class TestPublishPackages:
    def test_publish_packages_topological_order_and_masked_token(
        self, mock_monorepo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_publish_packages_topological_order_and_masked_token

        // Situation: publish_packages runs with --target pypi and valid auth token.
        // Expectation:
        //   1. All packages (db, admin, cli) are built into tmp_dist_dir.
        //   2. Clean-room verification runs (venv, install, import, cli).
        //   3. Packages are published strictly in topological order (db -> admin -> cli).
        //   4. UV_PUBLISH_TOKEN is passed in env; --token is NEVER in argv.
        """
        monkeypatch.setenv("PYPI_SECRET", "super-secret-token")
        executed_calls: list[dict] = []

        def mock_subprocess_run(
            cmd, cwd=None, env=None, capture_output=False, text=False, check=False
        ):
            executed_calls.append({"cmd": cmd, "cwd": cwd, "env": env})
            # Simulate creating wheel artifacts when uv build is called
            if cmd[:2] == ["uv", "build"]:
                out_dir = Path(cmd[cmd.index("--out-dir") + 1])
                pkg_name = Path(cwd).name.replace("-", "_")
                (out_dir / f"{pkg_name}-1.0.0-py3-none-any.whl").touch()
                (out_dir / f"{pkg_name}-1.0.0.tar.gz").touch()
            elif cmd[:2] == ["uv", "venv"]:
                venv_dir = Path(cmd[2])
                bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
                bin_dir.mkdir(parents=True, exist_ok=True)
                (bin_dir / "python").touch()
                (bin_dir / "datacommons").touch()
            return MagicMock(returncode=0, stdout="OK", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

        publisher.publish_packages(
            target="pypi", token_env="PYPI_SECRET", dry_run=False
        )

        # 1. Verify build calls (all 3 packages)
        build_calls = [c for c in executed_calls if c["cmd"][:2] == ["uv", "build"]]
        assert len(build_calls) == 3
        assert build_calls[0]["cwd"] == mock_monorepo / "packages/datacommons-db"
        assert build_calls[1]["cwd"] == mock_monorepo / "packages/datacommons-admin"
        assert build_calls[2]["cwd"] == mock_monorepo / "packages/datacommons-cli"

        # 2. Verify venv creation
        venv_calls = [c for c in executed_calls if c["cmd"][:2] == ["uv", "venv"]]
        assert len(venv_calls) == 1

        # 3. Verify pip install in sandbox
        install_calls = [
            c for c in executed_calls if c["cmd"][:3] == ["uv", "pip", "install"]
        ]
        assert len(install_calls) == 1
        assert any("datacommons_db" in arg for arg in install_calls[0]["cmd"])
        assert any("datacommons_admin" in arg for arg in install_calls[0]["cmd"])
        assert any("datacommons_cli" in arg for arg in install_calls[0]["cmd"])
        assert "--find-links" in install_calls[0]["cmd"]

        # 4. Verify module import test
        import_calls = [
            c for c in executed_calls if "-c" in c["cmd"] and "import" in c["cmd"][-1]
        ]
        assert len(import_calls) == 1
        assert (
            "import datacommons_db; import datacommons_admin; import datacommons_cli"
            in import_calls[0]["cmd"][-1]
        )

        # 5. Verify CLI entrypoint checks
        cli_calls = [
            c
            for c in executed_calls
            if Path(c["cmd"][0]).name.startswith("datacommons")
        ]
        assert len(cli_calls) == 3  # --version, --help, admin --help

        # 6. Verify topological publish calls and masked token
        publish_calls = [c for c in executed_calls if c["cmd"][:2] == ["uv", "publish"]]
        assert len(publish_calls) == 3
        assert "datacommons_db" in publish_calls[0]["cmd"][-1]
        assert "datacommons_admin" in publish_calls[1]["cmd"][-1]
        assert "datacommons_cli" in publish_calls[2]["cmd"][-1]
        for p_call in publish_calls:
            assert "--token" not in p_call["cmd"]
            assert p_call["env"]["UV_PUBLISH_TOKEN"] == "super-secret-token"

    def test_publish_packages_testpypi_url_flag(
        self, mock_monorepo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_publish_packages_testpypi_url_flag

        // Situation: publish_packages runs targeting testpypi.
        // Expectation: --publish-url https://test.pypi.org/legacy/ is appended to uv
        publish command.
        """
        monkeypatch.setenv("TEST_PYPI_TOKEN", "mock-test-token")
        executed_cmds: list[list[str]] = []

        def mock_subprocess_run(
            cmd, cwd=None, env=None, capture_output=False, text=False, check=False
        ):
            executed_cmds.append(cmd)
            if cmd[:2] == ["uv", "build"]:
                out_dir = Path(cmd[cmd.index("--out-dir") + 1])
                pkg_name = Path(cwd).name.replace("-", "_")
                (out_dir / f"{pkg_name}-1.0.0-py3-none-any.whl").touch()
                (out_dir / f"{pkg_name}-1.0.0.tar.gz").touch()
            elif cmd[:2] == ["uv", "venv"]:
                venv_dir = Path(cmd[2])
                bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
                bin_dir.mkdir(parents=True, exist_ok=True)
                (bin_dir / "python").touch()
                (bin_dir / "datacommons").touch()
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

        publisher.publish_packages(
            target="testpypi", token_env="TEST_PYPI_TOKEN", dry_run=False
        )

        publish_cmds = [cmd for cmd in executed_cmds if cmd[:2] == ["uv", "publish"]]
        assert len(publish_cmds) == 3
        for cmd in publish_cmds:
            assert "--publish-url" in cmd
            assert "https://test.pypi.org/legacy/" in cmd

    def test_publish_packages_dry_run_skips_uploads(
        self,
        mock_monorepo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """// Test: test_publish_packages_dry_run_skips_uploads

        // Situation: publish_packages runs with dry_run=True.
        // Expectation: Runs builds and sandbox verification but makes zero uv publish calls.
        """
        executed_cmds: list[list[str]] = []

        def mock_subprocess_run(
            cmd, cwd=None, env=None, capture_output=False, text=False, check=False
        ):
            executed_cmds.append(cmd)
            if cmd[:2] == ["uv", "build"]:
                out_dir = Path(cmd[cmd.index("--out-dir") + 1])
                pkg_name = Path(cwd).name.replace("-", "_")
                (out_dir / f"{pkg_name}-1.0.0-py3-none-any.whl").touch()
                (out_dir / f"{pkg_name}-1.0.0.tar.gz").touch()
            elif cmd[:2] == ["uv", "venv"]:
                venv_dir = Path(cmd[2])
                bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
                bin_dir.mkdir(parents=True, exist_ok=True)
                (bin_dir / "python").touch()
                (bin_dir / "datacommons").touch()
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

        publisher.publish_packages(target="pypi", token_env=None, dry_run=True)

        publish_cmds = [cmd for cmd in executed_cmds if cmd[:2] == ["uv", "publish"]]
        assert len(publish_cmds) == 0
        captured = capsys.readouterr().out
        assert "[DRY RUN - VERIFY ONLY]" in captured
        assert (
            "Clean-room pre-publish verification succeeded for all packages" in captured
        )

    @pytest.mark.parametrize(
        ("token_env_name", "env_dict", "expected_err"),
        [
            (None, {}, "--token-env is required"),
            ("MISSING_VAR", {}, "is not set or empty"),
            ("EMPTY_VAR", {"EMPTY_VAR": ""}, "is not set or empty"),
        ],
    )
    def test_publish_packages_token_env_errors(
        self,
        mock_monorepo: Path,
        monkeypatch: pytest.MonkeyPatch,
        token_env_name: str | None,
        env_dict: dict[str, str],
        expected_err: str,
    ) -> None:
        """// Test: test_publish_packages_token_env_errors

        // Situation: Token environment variable is omitted, missing, or empty
        during non-dry run.
        // Expectation: Script aborts with clear error message.
        """
        for k, v in env_dict.items():
            monkeypatch.setenv(k, v)

        with pytest.raises(SystemExit) as exc_info:
            publisher.publish_packages(
                target="pypi", token_env=token_env_name, dry_run=False
            )

        assert expected_err in str(exc_info.value)

    def test_publish_packages_build_failure_aborts_immediately(
        self, mock_monorepo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_publish_packages_build_failure_aborts_immediately

        // Situation: uv build fails on datacommons-admin.
        // Expectation: Script aborts with exit code 1 and subsequent steps are skipped.
        """

        def failing_run(cmd, cwd=None, **kwargs):
            if cmd[:2] == ["uv", "build"] and Path(cwd).name == "datacommons-admin":
                return MagicMock(returncode=1, stderr="Build syntax error")
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", failing_run)

        with pytest.raises(SystemExit) as exc_info:
            publisher.publish_packages(target="pypi", token_env=None, dry_run=True)

        assert exc_info.value.code == 1

    def test_publish_packages_install_failure_aborts(
        self,
        mock_monorepo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """// Test: test_publish_packages_install_failure_aborts

        // Situation: uv pip install in sandbox fails (e.g. missing dependency datacommons-db).
        // Expectation: Script aborts with exit code 1, prints diagnostic banner, and skips publish.
        """

        def failing_run(cmd, cwd=None, **kwargs):
            if cmd[:2] == ["uv", "build"]:
                out_dir = Path(cmd[cmd.index("--out-dir") + 1])
                pkg_name = Path(cwd).name.replace("-", "_")
                (out_dir / f"{pkg_name}-1.0.0-py3-none-any.whl").touch()
            elif cmd[:2] == ["uv", "venv"]:
                venv_dir = Path(cmd[2])
                bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
                bin_dir.mkdir(parents=True, exist_ok=True)
                (bin_dir / "python").touch()
            elif cmd[:3] == ["uv", "pip", "install"]:
                return MagicMock(
                    returncode=1,
                    stderr="No matching distribution found for datacommons-db",
                )
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", failing_run)

        with pytest.raises(SystemExit) as exc_info:
            publisher.publish_packages(target="pypi", token_env=None, dry_run=True)

        assert exc_info.value.code == 1
        captured = capsys.readouterr().out
        assert (
            "PRE-PUBLISH VERIFICATION FAILED: Dependency Resolution / Install Error"
            in captured
        )
        assert "No matching distribution found for datacommons-db" in captured

    def test_publish_packages_import_failure_aborts(
        self,
        mock_monorepo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """// Test: test_publish_packages_import_failure_aborts

        // Situation: Module import fails in sandbox (e.g. missing schema.sql asset).
        // Expectation: Script aborts with exit code 1, prints diagnostic banner, and skips publish.
        """

        def failing_run(cmd, cwd=None, **kwargs):
            if cmd[:2] == ["uv", "build"]:
                out_dir = Path(cmd[cmd.index("--out-dir") + 1])
                pkg_name = Path(cwd).name.replace("-", "_")
                (out_dir / f"{pkg_name}-1.0.0-py3-none-any.whl").touch()
            elif cmd[:2] == ["uv", "venv"]:
                venv_dir = Path(cmd[2])
                bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
                bin_dir.mkdir(parents=True, exist_ok=True)
                (bin_dir / "python").touch()
            elif "-c" in cmd and "import" in cmd[-1]:
                return MagicMock(
                    returncode=1, stderr="FileNotFoundError: No such file 'schema.sql'"
                )
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", failing_run)

        with pytest.raises(SystemExit) as exc_info:
            publisher.publish_packages(target="pypi", token_env=None, dry_run=True)

        assert exc_info.value.code == 1
        captured = capsys.readouterr().out
        assert (
            "PRE-PUBLISH VERIFICATION FAILED: Module Import / Runtime Asset Error"
            in captured
        )
        assert "FileNotFoundError" in captured

    def test_publish_packages_cli_smoke_failure_aborts(
        self,
        mock_monorepo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """// Test: test_publish_packages_cli_smoke_failure_aborts

        // Situation: CLI command crashes during smoke test.
        // Expectation: Script aborts with exit code 1, prints diagnostic banner, and skips publish.
        """

        def failing_run(cmd, cwd=None, **kwargs):
            if cmd[:2] == ["uv", "build"]:
                out_dir = Path(cmd[cmd.index("--out-dir") + 1])
                pkg_name = Path(cwd).name.replace("-", "_")
                (out_dir / f"{pkg_name}-1.0.0-py3-none-any.whl").touch()
            elif cmd[:2] == ["uv", "venv"]:
                venv_dir = Path(cmd[2])
                bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
                bin_dir.mkdir(parents=True, exist_ok=True)
                (bin_dir / "python").touch()
                (bin_dir / "datacommons").touch()
            elif Path(cmd[0]).name.startswith("datacommons") and "--version" in cmd:
                return MagicMock(
                    returncode=1,
                    stderr="Traceback (most recent call last): RuntimeError: corrupted entrypoint",
                )
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", failing_run)

        with pytest.raises(SystemExit) as exc_info:
            publisher.publish_packages(target="pypi", token_env=None, dry_run=True)

        assert exc_info.value.code == 1
        captured = capsys.readouterr().out
        assert (
            "PRE-PUBLISH VERIFICATION FAILED: CLI command 'datacommons --version' crashed"
            in captured
        )

    def test_publish_packages_missing_cli_binary_aborts(
        self,
        mock_monorepo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """// Test: test_publish_packages_missing_cli_binary_aborts

        // Situation: datacommons-cli is published but datacommons binary was not created.
        // Expectation: Script aborts with exit code 1, prints diagnostic message, and skips publish.
        """

        def failing_run(cmd, cwd=None, **kwargs):
            if cmd[:2] == ["uv", "build"]:
                out_dir = Path(cmd[cmd.index("--out-dir") + 1])
                pkg_name = Path(cwd).name.replace("-", "_")
                (out_dir / f"{pkg_name}-1.0.0-py3-none-any.whl").touch()
            elif cmd[:2] == ["uv", "venv"]:
                venv_dir = Path(cmd[2])
                bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
                bin_dir.mkdir(parents=True, exist_ok=True)
                (bin_dir / "python").touch()
                # Simulate datacommons binary missing (e.g. broken console_scripts)
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", failing_run)

        with pytest.raises(SystemExit) as exc_info:
            publisher.publish_packages(target="pypi", token_env=None, dry_run=True)

        assert exc_info.value.code == 1
        captured = capsys.readouterr().out
        assert (
            "PRE-PUBLISH VERIFICATION FAILED: CLI entrypoint 'datacommons' was not created"
            in captured
        )


# ==============================================================================
# Suite 4: End-to-End Round-Trip Integration Contract
# ==============================================================================


class TestReleaseWorkflowContract:
    @pytest.mark.parametrize("target_version", ["1.2.3", "v1.2.3", "2.0.0rc1"])
    def test_e2e_bump_then_validate_roundtrip(
        self, mock_monorepo: Path, target_version: str
    ) -> None:
        """// Test: test_e2e_bump_then_validate_roundtrip

        // Situation: A release engineer runs apply_version_bump followed
        immediately by validate_release_version.
        // Expectation: The bumper and validator execute with zero contract drift or
        formatting divergence.
        """
        bumper.apply_version_bump(target_version)
        validator.validate_release_version(target_version)
        validator.validate_release_version(target_version.lstrip("v"))


# ==============================================================================
# Suite 5: tag_release_artifacts.py
# ==============================================================================


class TestTagReleaseArtifacts:
    def test_tag_all_artifacts_dry_run_success(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """// Test: test_tag_all_artifacts_dry_run_success

        // Situation: tag_all_artifacts is called with a default baseline and a
        services override in dry-run mode.
        // Expectation: All container images and the template are planned correctly and
        displayed in output.
        """
        tagger.tag_all_artifacts(
            target_tag="1.1.2rc1",
            default_source_tag="1.1.1",
            services_tag="1574ed3-79627f8-e265a1d",
            dry_run=True,
        )
        captured = capsys.readouterr().out
        assert "RELEASE ARTIFACT TAGGING PLAN -> Target: '1.1.2rc1'" in captured
        assert "services          : 1574ed3-79627f8-e265a1d -> 1.1.2rc1" in captured
        assert "preprocessor      : 1.1.1 -> 1.1.2rc1" in captured
        assert "postprocessor     : 1.1.1 -> 1.1.2rc1" in captured
        assert "ingestion_helper  : 1.1.1 -> 1.1.2rc1" in captured
        assert "dataflow_image    : [from template 1.1.1] -> 1.1.2rc1" in captured
        assert "ingestion-1.1.1.json -> ingestion-1.1.2rc1.json" in captured
        assert "gcloud container images add-tag" in captured
        assert "[DRY-RUN]" in captured
        assert "Dry-run complete. No artifacts were modified." in captured
        assert "All release artifacts tagged and staged successfully!" not in captured

    def test_tag_all_artifacts_wholesale_promotion(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """// Test: test_tag_all_artifacts_wholesale_promotion

        // Situation: tag_all_artifacts is called to promote RC candidate 1.1.2rc2 to
        production 1.1.2.
        // Expectation: All artifacts inherit 1.1.2rc2 as the source tag.
        """
        tagger.tag_all_artifacts(
            target_tag="1.1.2",
            default_source_tag="1.1.2rc2",
            dry_run=True,
        )
        captured = capsys.readouterr().out
        assert "services          : 1.1.2rc2 -> 1.1.2" in captured
        assert "preprocessor      : 1.1.2rc2 -> 1.1.2" in captured
        assert "postprocessor     : 1.1.2rc2 -> 1.1.2" in captured
        assert "ingestion_helper  : 1.1.2rc2 -> 1.1.2" in captured
        assert "dataflow_image    : [from template 1.1.2rc2] -> 1.1.2" in captured
        assert "ingestion-1.1.2rc2.json -> ingestion-1.1.2.json" in captured

    def test_tag_all_artifacts_redirects_dataflow_latest_to_stable(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """// Test: test_tag_all_artifacts_redirects_dataflow_latest_to_stable

        // Situation: tag_all_artifacts is called with default_source_tag="latest".
        // Expectation: dataflow template redirects to 'stable', while other images preserve 'latest'.
        """
        tagger.tag_all_artifacts(
            target_tag="1.1.2rc1",
            default_source_tag="latest",
            dry_run=True,
        )
        captured = capsys.readouterr().out
        assert "services          : latest -> 1.1.2rc1" in captured
        assert "preprocessor      : latest -> 1.1.2rc1" in captured
        assert "postprocessor     : latest -> 1.1.2rc1" in captured
        assert "ingestion_helper  : latest -> 1.1.2rc1" in captured
        assert "dataflow_image    : [from template stable] -> 1.1.2rc1" in captured
        assert "ingestion-stable.json -> ingestion-1.1.2rc1.json" in captured

    def test_tag_all_artifacts_dataflow_override_latest_to_stable(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """// Test: test_tag_all_artifacts_dataflow_override_latest_to_stable

        // Situation: dataflow_template_tag="latest" is explicitly passed with a different default_source_tag.
        // Expectation: dataflow template spec redirects to 'stable'.
        """
        tagger.tag_all_artifacts(
            target_tag="1.1.2rc1",
            default_source_tag="1.1.1",
            dataflow_template_tag="latest",
            dry_run=True,
        )
        captured = capsys.readouterr().out
        assert "services          : 1.1.1 -> 1.1.2rc1" in captured
        assert "dataflow_image    : [from template stable] -> 1.1.2rc1" in captured
        assert "ingestion-stable.json -> ingestion-1.1.2rc1.json" in captured

    def test_tag_all_artifacts_explicit_dataflow_image_override(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """// Test: test_tag_all_artifacts_explicit_dataflow_image_override

        // Situation: dataflow_image_tag="custom-worker-sha" is explicitly provided.
        // Expectation: Plan shows custom-worker-sha as dataflow_image source.
        """
        tagger.tag_all_artifacts(
            target_tag="1.1.2rc1",
            default_source_tag="latest",
            dataflow_image_tag="custom-worker-sha",
            dry_run=True,
        )
        captured = capsys.readouterr().out
        assert "dataflow_image    : custom-worker-sha -> 1.1.2rc1" in captured
        assert "ingestion-stable.json -> ingestion-1.1.2rc1.json" in captured
        assert "custom-worker-sha (explicit override)" in captured

    def test_tag_all_artifacts_preserves_explicit_dataflow_version(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """// Test: test_tag_all_artifacts_preserves_explicit_dataflow_version

        // Situation: An explicit non-latest dataflow_template_tag is passed when default_source_tag="latest".
        // Expectation: dataflow template uses the explicit tag without redirecting to 'stable'.
        """
        tagger.tag_all_artifacts(
            target_tag="1.1.2rc1",
            default_source_tag="latest",
            dataflow_template_tag="1.1.0",
            dry_run=True,
        )
        captured = capsys.readouterr().out
        assert "services          : latest -> 1.1.2rc1" in captured
        assert "dataflow_image    : [from template 1.1.0] -> 1.1.2rc1" in captured
        assert "ingestion-1.1.0.json -> ingestion-1.1.2rc1.json" in captured

    def test_tag_all_artifacts_missing_source_tag_aborts(self) -> None:
        """// Test: test_tag_all_artifacts_missing_source_tag_aborts

        // Situation: tag_all_artifacts is called without a default source tag and
        missing individual overrides.
        // Expectation: Script calls sys.exit reporting missing source tags.
        """
        with pytest.raises(SystemExit) as exc_info:
            tagger.tag_all_artifacts(
                target_tag="1.1.2rc1",
                services_tag="1574ed3",
            )
        assert "Missing source tag for artifact(s)" in str(exc_info.value)

    @pytest.mark.parametrize("malformed_target", ["foo", "1.2", "1.2.3.4.5", ""])
    def test_tag_all_artifacts_malformed_target_tag_aborts(
        self, malformed_target: str
    ) -> None:
        """// Test: test_tag_all_artifacts_malformed_target_tag_aborts

        // Situation: tag_all_artifacts is called with an invalid/malformed target tag.
        // Expectation: Script calls sys.exit rejecting invalid version format.
        """
        with pytest.raises(SystemExit) as exc_info:
            tagger.tag_all_artifacts(
                target_tag=malformed_target,
                default_source_tag="1.1.1",
            )
        assert "Invalid target tag format" in str(
            exc_info.value
        ) or "Target tag cannot be empty" in str(exc_info.value)

    def test_stage_dataflow_artifacts_dynamic_image_resolution_and_tagging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_stage_dataflow_artifacts_dynamic_image_resolution_and_tagging

        // Situation: stage_dataflow_artifacts downloads template JSON, extracts underlying
        image reference, tags the image in Artifact Registry, and uploads new template.
        // Expectation: The image from JSON is tagged and the uploaded JSON points to target tag.
        """
        source_json = tmp_path / "ingestion-stable.json"
        source_json.write_text(
            json.dumps(
                {
                    "image": (
                        "us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:f756c2f"
                    ),
                    "sdk_info": {"language": "JAVA"},
                },
                indent=2,
            )
        )

        uploaded_content = {}
        executed_cmds = []

        def mock_gcloud_run(cmd, **kwargs):
            executed_cmds.append(cmd)
            if cmd[0] == "gcloud" and cmd[1] == "storage" and cmd[2] == "cp":
                src = cmd[3]
                dst = cmd[4]
                if src.startswith("gs://"):
                    Path(dst).write_text(source_json.read_text())
                elif dst.startswith("gs://"):
                    uploaded_content["data"] = json.loads(Path(src).read_text())
                return MagicMock(returncode=0)
            elif cmd[0] == "gcloud" and cmd[1] == "artifacts":
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", mock_gcloud_run)

        tagger.stage_dataflow_artifacts(
            gcs_base="gs://datcom-templates/templates/flex",
            template_tag="stable",
            target_tag="1.1.3rc2",
            dataflow_image_repo="us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion",
            dry_run=False,
        )

        # 1. Verify docker tag call used extracted image
        tag_calls = [
            c
            for c in executed_cmds
            if len(c) >= 6
            and c[0] == "gcloud"
            and c[1] == "artifacts"
            and c[2] == "docker"
        ]
        assert len(tag_calls) == 1
        assert (
            tag_calls[0][5]
            == "us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:f756c2f"
        )
        assert (
            tag_calls[0][6]
            == "us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:1.1.3rc2"
        )

        # 2. Verify uploaded template JSON
        assert (
            uploaded_content["data"]["image"]
            == "us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:1.1.3rc2"
        )
        assert uploaded_content["data"]["sdk_info"]["language"] == "JAVA"

    def test_stage_dataflow_artifacts_explicit_image_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_stage_dataflow_artifacts_explicit_image_override

        // Situation: stage_dataflow_artifacts is called with explicit image_tag="custom-sha".
        // Expectation: The explicit image is tagged instead of reading template['image'].
        """
        source_json = tmp_path / "ingestion-stable.json"
        source_json.write_text(
            json.dumps(
                {
                    "image": (
                        "us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:old-sha"
                    ),
                },
                indent=2,
            )
        )

        executed_cmds = []

        def mock_gcloud_run(cmd, **kwargs):
            executed_cmds.append(cmd)
            if cmd[0] == "gcloud" and cmd[1] == "storage" and cmd[2] == "cp":
                src = cmd[3]
                dst = cmd[4]
                if src.startswith("gs://"):
                    Path(dst).write_text(source_json.read_text())
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", mock_gcloud_run)

        tagger.stage_dataflow_artifacts(
            gcs_base="gs://datcom-templates/templates/flex",
            template_tag="stable",
            target_tag="1.1.3rc2",
            image_tag="custom-sha",
            dataflow_image_repo="us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion",
            dry_run=False,
        )

        tag_calls = [
            c
            for c in executed_cmds
            if len(c) >= 6
            and c[0] == "gcloud"
            and c[1] == "artifacts"
            and c[2] == "docker"
        ]
        assert len(tag_calls) == 1
        assert (
            tag_calls[0][5]
            == "us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:custom-sha"
        )
        assert (
            tag_calls[0][6]
            == "us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:1.1.3rc2"
        )

    def test_stage_dataflow_artifacts_missing_image_in_template_aborts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_stage_dataflow_artifacts_missing_image_in_template_aborts

        // Situation: Downloaded template JSON has no 'image' field.
        // Expectation: Script aborts with clear error message.
        """
        no_image_json = tmp_path / "no_image.json"
        no_image_json.write_text(json.dumps({"metadata": {}}))

        def mock_gcloud_run(cmd, **kwargs):
            if cmd[0] == "gcloud" and cmd[1] == "storage" and cmd[2] == "cp":
                dst = cmd[4]
                Path(dst).write_text(no_image_json.read_text())
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", mock_gcloud_run)

        with pytest.raises(SystemExit) as exc_info:
            tagger.stage_dataflow_artifacts(
                gcs_base="gs://datcom-templates/templates/flex",
                template_tag="stable",
                target_tag="1.1.3rc2",
                dataflow_image_repo="us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion",
                dry_run=False,
            )
        assert "missing valid 'image' property" in str(exc_info.value)

    def test_tag_container_image_failure_aborts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_tag_container_image_failure_aborts

        // Situation: gcloud container images add-tag fails with exit code 1.
        // Expectation: Script calls sys.exit reporting the command failure.
        """

        def failing_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd, stderr="Image not found")

        monkeypatch.setattr(subprocess, "run", failing_run)

        with pytest.raises(SystemExit) as exc_info:
            tagger.tag_container_image(
                repo="gcr.io/datcom-ci/datacommons-services",
                src_tag="missing-tag",
                target_tag="1.1.2",
            )
        assert "Failed to tag image" in str(exc_info.value)

    def test_stage_dataflow_template_non_dict_json_aborts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_stage_dataflow_template_non_dict_json_aborts

        // Situation: Downloaded template JSON is a list instead of a dictionary.
        // Expectation: Script aborts with clear error message.
        """
        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text(json.dumps(["item1", "item2"]))

        def mock_gcloud_run(cmd, **kwargs):
            if cmd[0] == "gcloud" and cmd[1] == "storage" and cmd[2] == "cp":
                dst = cmd[4]
                Path(dst).write_text(invalid_json.read_text())
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", mock_gcloud_run)

        with pytest.raises(SystemExit) as exc_info:
            tagger.stage_dataflow_artifacts(
                gcs_base="gs://datcom-templates/templates/flex",
                template_tag="1.1.1",
                target_tag="1.1.2",
                dataflow_image_repo="us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion",
                dry_run=False,
            )
        assert "Template JSON root must be a dictionary object" in str(exc_info.value)

    def test_tag_all_artifacts_missing_gcloud_aborts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """// Test: test_tag_all_artifacts_missing_gcloud_aborts

        // Situation: tag_all_artifacts runs with dry_run=False but gcloud is not installed.
        // Expectation: Script aborts reporting missing gcloud CLI.
        """
        monkeypatch.setattr(
            shutil,
            "which",
            lambda cmd: None if cmd == "gcloud" else "/usr/bin/" + cmd,
        )
        with pytest.raises(SystemExit) as exc_info:
            tagger.tag_all_artifacts(
                target_tag="1.1.2",
                default_source_tag="1.1.1",
                dry_run=False,
            )
        assert "gcloud" in str(exc_info.value)
