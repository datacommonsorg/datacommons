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

import dataclasses
import json
import re
from pathlib import Path

import pytest
from datacommons_admin.core.utils import tf_utils
from datacommons_admin.core.utils.models import TerraformOutputs


def extract_tf_outputs(tf_file_path: Path) -> set[str]:
    """Robustly extracts declared output names from a Terraform HCL file, stripping comments."""
    content = tf_file_path.read_text(encoding="utf-8")
    # 1. Strip multi-line block comments /* ... */
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    # 2. Strip single-line comments # ... and // ...
    content = re.sub(r"(#|//).*?$", "", content, flags=re.MULTILINE)
    # 3. Match top-level output declarations
    matches = re.findall(
        r'^\s*output\s+["\']?([a-zA-Z0-9_-]+)["\']?\s*\{',
        content,
        flags=re.MULTILINE,
    )
    return set(matches)


@pytest.fixture
def repo_root() -> Path:
    """Finds the root of the datcom-datacommons repository."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "infra" / "dcp" / "outputs.tf").exists():
            return current
        current = current.parent
    raise FileNotFoundError(
        "Could not find repository root containing infra/dcp/outputs.tf"
    )


def test_terraform_outputs_dataclass_contract(repo_root: Path) -> None:
    """Verifies that all fields defined in TerraformOutputs are declared in infra/dcp/outputs.tf."""
    tf_outputs_file = repo_root / "infra" / "dcp" / "outputs.tf"
    assert tf_outputs_file.exists(), (
        f"Terraform outputs file not found: {tf_outputs_file}"
    )

    declared_outputs = extract_tf_outputs(tf_outputs_file)
    dataclass_fields = {f.name for f in dataclasses.fields(TerraformOutputs)}

    missing_in_tf = dataclass_fields - declared_outputs
    assert not missing_in_tf, (
        f"The following fields in TerraformOutputs are NOT declared in {tf_outputs_file}:\n"
        f"{sorted(missing_in_tf)}\n"
        "Either export these outputs in infra/dcp/outputs.tf or update TerraformOutputs."
    )


def test_tf_utils_constants_contract(repo_root: Path) -> None:
    """Verifies that all TF_OUTPUT_* constants in tf_utils are declared in infra/dcp/outputs.tf."""
    tf_outputs_file = repo_root / "infra" / "dcp" / "outputs.tf"
    declared_outputs = extract_tf_outputs(tf_outputs_file)

    tf_utils_constants = {
        value
        for name, value in vars(tf_utils).items()
        if name.startswith("TF_OUTPUT_") and isinstance(value, str)
    }

    missing_in_tf = tf_utils_constants - declared_outputs
    assert not missing_in_tf, (
        f"The following TF_OUTPUT_* constants in tf_utils are NOT declared in {tf_outputs_file}:\n"
        f"{sorted(missing_in_tf)}"
    )


def test_root_and_module_outputs_parity(repo_root: Path) -> None:
    """Verifies that outputs in infra/dcp/outputs.tf delegating to module.stack exist in the stack module."""
    root_outputs_file = repo_root / "infra" / "dcp" / "outputs.tf"
    stack_outputs_file = (
        repo_root / "infra" / "dcp" / "modules" / "stack" / "outputs.tf"
    )

    assert root_outputs_file.exists(), (
        f"Root outputs file not found: {root_outputs_file}"
    )
    assert stack_outputs_file.exists(), (
        f"Stack module outputs file not found: {stack_outputs_file}"
    )

    root_content = root_outputs_file.read_text(encoding="utf-8")
    delegated_matches = re.findall(
        r"value\s*=\s*module\.stack\.([a-zA-Z0-9_-]+)",
        root_content,
    )
    delegated_outputs = set(delegated_matches)
    stack_declared_outputs = extract_tf_outputs(stack_outputs_file)

    missing_in_stack = delegated_outputs - stack_declared_outputs
    assert not missing_in_stack, (
        f"The following outputs are delegated via module.stack in {root_outputs_file}, "
        f"but are NOT declared in {stack_outputs_file}:\n"
        f"{sorted(missing_in_stack)}"
    )


def test_conftest_fixtures_in_sync_with_contract(
    mock_tf_output_spanner: str,
    mock_tf_output_ingest: str,
    repo_root: Path,
) -> None:
    """Verifies that mock fixtures in conftest.py instantiate TerraformOutputs and match outputs.tf."""
    tf_outputs_file = repo_root / "infra" / "dcp" / "outputs.tf"
    declared_outputs = extract_tf_outputs(tf_outputs_file)

    for fixture_name, fixture_json in [
        ("mock_tf_output_spanner", mock_tf_output_spanner),
        ("mock_tf_output_ingest", mock_tf_output_ingest),
    ]:
        raw_dict = json.loads(fixture_json)
        fixture_keys = set(raw_dict.keys())
        invalid_keys = fixture_keys - declared_outputs
        assert not invalid_keys, (
            f"Fixture '{fixture_name}' contains keys NOT declared in {tf_outputs_file}:\n"
            f"{sorted(invalid_keys)}"
        )

        outputs_obj = TerraformOutputs.from_state_outputs(raw_dict)
        assert outputs_obj.project_id == "mock-proj"
        assert outputs_obj.ingestion_temp_location == "gs://mock-bucket/temp"
