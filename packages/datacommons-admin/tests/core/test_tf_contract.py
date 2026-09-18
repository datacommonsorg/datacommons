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

"""Contract tests enforcing synchronization between Terraform outputs and Admin CLI models.

This module statically parses `infra/dcp/outputs.tf` to verify that every attribute
defined on the `TerraformOutputs` dataclass is declared in root `outputs.tf`.
"""

import dataclasses
import re
from pathlib import Path

import click
import pytest
from datacommons_admin.core.terraform.models import TerraformOutputs


def _strip_hcl_comments(content: str) -> str:
    """Strips multi-line (/* ... */) and single-line (# ..., // ...) HCL comments."""
    # 1. Strip multi-line block comments /* ... */
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    # 2. Strip single-line comments # ... and // ...
    return re.sub(r"(#|//).*?$", "", content, flags=re.MULTILINE)


def extract_tf_outputs(tf_file_path: Path) -> set[str]:
    """Robustly extracts declared output names from a Terraform HCL file, stripping comments."""
    content = _strip_hcl_comments(tf_file_path.read_text(encoding="utf-8"))
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


def test_terraform_outputs_from_state_outputs_edge_cases() -> None:
    """Verifies missing required fields raise ClickException and optional fields use defaults."""
    base_valid = {
        "project_id": {"value": "  test-proj  "},
        "region": "us-central1",
        "ingestion_service_url": {"value": "https://service"},
        "ingestion_workflow_name": {"value": "wf"},
        "ingestion_workflow_service_account_email": {"value": "sa@test.com"},
        "storage_artifacts_bucket_name": {"value": "bucket"},
        "ingestion_artifacts_path": {"value": "artifacts"},
    }

    parsed = TerraformOutputs.from_state_outputs(base_valid)
    assert parsed.project_id == "test-proj"
    assert parsed.ingestion_temp_location == "gs://bucket/artifacts/temp"
    assert parsed.spanner_instance_id is None
    assert parsed.spanner_database_id is None
    assert parsed.ingestion_prep_job_name is None

    # Missing or whitespace-only required field raises ClickException
    invalid_missing = {**base_valid, "project_id": {"value": "   "}}
    with pytest.raises(
        click.ClickException,
        match="Required Terraform output 'project_id' is missing or empty",
    ):
        TerraformOutputs.from_state_outputs(invalid_missing)
