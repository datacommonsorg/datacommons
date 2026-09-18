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
from dataclasses import dataclass
from typing import Any

import click


# frozen=True ensures parsed deployment outputs cannot be mutated accidentally across CLI commands or helpers.
@dataclass(frozen=True)
class TerraformOutputs:
    """Strongly typed, validated deployment outputs matching infra/dcp/outputs.tf.

    Rule for Required vs. Optional Attributes:
      - Required fields (no default): Must correspond to unconditional Terraform outputs
        in infra/dcp/outputs.tf that are guaranteed to be non-null in every deployment.
      - Optional fields (with default None): Must correspond to conditional Terraform
        outputs in infra/dcp/modules/stack/outputs.tf whose HCL expressions can evaluate
        to null when a feature/module is disabled (e.g., var.spanner_config.enable ? ... : null).
    """

    # Unconditional outputs (always present in every deployment)
    project_id: str
    region: str
    ingestion_service_url: str
    ingestion_workflow_name: str
    ingestion_workflow_service_account_email: str
    storage_artifacts_bucket_name: str
    ingestion_artifacts_path: str

    # Conditional outputs (can evaluate to null in HCL when feature is disabled)
    spanner_instance_id: str | None = None
    spanner_database_id: str | None = None
    ingestion_prep_job_name: str | None = None

    @property
    def ingestion_temp_location(self) -> str:
        """Derived convenience property computing the canonical GCS path for temporary workflow artifacts.

        Note: TEMP_LOCATION is not exported as its own key in outputs.tf; Terraform defines it
        in modules/stack/main.tf as
        'gs://${module.storage.artifacts_bucket_name}/${var.ingestion_config.ingestion_artifacts_path}/temp'.
        """
        return f"gs://{self.storage_artifacts_bucket_name}/{self.ingestion_artifacts_path}/temp"

    @classmethod
    def from_state_outputs(cls, raw_outputs: dict[str, Any]) -> "TerraformOutputs":
        """Extracts scalar values from Terraform's JSON output objects, strips whitespace, and validates fields."""
        parsed_fields: dict[str, Any] = {}

        for field_def in dataclasses.fields(cls):
            key = field_def.name
            entry = raw_outputs.get(key)
            # Terraform JSON format represents each output as {"value": <val>, "type": ..., "sensitive": ...}.
            # Support both standard Terraform output objects and flat key-value test dictionaries.
            val = (
                entry.get("value")
                if isinstance(entry, dict) and "value" in entry
                else entry
            )

            if isinstance(val, str):
                val = val.strip()

            if val is None or val == "":
                if field_def.default is not dataclasses.MISSING:
                    parsed_fields[key] = field_def.default
                else:
                    raise click.ClickException(
                        f"Required Terraform output '{key}' is missing or empty in deployment state."
                    )
            else:
                parsed_fields[key] = str(val)

        return cls(**parsed_fields)
