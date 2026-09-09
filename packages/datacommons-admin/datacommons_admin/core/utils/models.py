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
from pathlib import Path
from typing import Any

import click

from datacommons_admin.init.utils.gcs_utils import get_default_state_uri


@dataclass(frozen=True)
class TerraformStateConfig:
    """Encapsulates and validates configuration parameters for locating Terraform state.

    Attributes:
        project_id: GCP project ID used for canonical bucket derivation and GCS client auth.
        instance_name: DCP instance name prefix used for canonical bucket and object path derivation.
        tf_state_location: Explicit GCS URI pointing directly to the Terraform state file.
    """

    project_id: str | None = None
    instance_name: str | None = None
    tf_state_location: str | None = None

    def __post_init__(self) -> None:
        """Validates configuration combinations upon initialization."""
        if not self.tf_state_location and (
            bool(self.project_id) != bool(self.instance_name)
        ):
            raise click.ClickException(
                "Both --project-id and --instance-name must be specified together to locate remote state."
            )

    @property
    def is_remote(self) -> bool:
        """Determines whether remote GCS state resolution should be used."""
        return bool(self.tf_state_location or (self.project_id and self.instance_name))

    @property
    def gcs_uri(self) -> str:
        """Computes the fully qualified GCS URI for remote state."""
        if self.tf_state_location:
            return self.tf_state_location

        if self.project_id and self.instance_name:
            return get_default_state_uri(self.project_id, self.instance_name)

        raise click.ClickException(
            "Cannot compute GCS URI for local Terraform state configuration."
        )

    @property
    def location_description(self) -> str:
        """Returns a human-readable description of the state location for error messages."""
        if self.tf_state_location:
            return f"GCS URI '{self.tf_state_location}'"
        if self.project_id and self.instance_name:
            return (
                f"GCP project: '{self.project_id}' / instance: '{self.instance_name}'"
            )
        return f"'{Path.cwd()}'"


@dataclass(frozen=True)
class TerraformOutputs:
    """Strongly typed, validated deployment outputs matching infra/dcp/outputs.tf."""

    project_id: str
    region: str
    ingestion_service_url: str
    ingestion_workflow_name: str
    ingestion_workflow_service_account_email: str
    storage_artifacts_bucket_name: str
    spanner_instance_id: str = ""
    spanner_database_id: str = ""
    ingestion_prep_job_name: str | None = None

    @property
    def ingestion_temp_location(self) -> str:
        """Derived canonical GCS path for workflow temporary artifacts."""
        return f"gs://{self.storage_artifacts_bucket_name}/temp"

    @classmethod
    def from_state_outputs(cls, raw_outputs: dict[str, Any]) -> "TerraformOutputs":
        """Unwraps Terraform output values, strips whitespace, and instantiates the dataclass."""
        unwrapped: dict[str, Any] = {}
        fields = cls.__dataclass_fields__

        for key, field_def in fields.items():
            entry = raw_outputs.get(key)
            val = (
                entry.get("value")
                if isinstance(entry, dict) and "value" in entry
                else entry
            )

            if isinstance(val, str):
                val = val.strip()

            if val is None or val == "":
                if field_def.default is not dataclasses.MISSING:
                    unwrapped[key] = field_def.default
                elif field_def.default_factory is not dataclasses.MISSING:
                    unwrapped[key] = field_def.default_factory()
                else:
                    raise click.ClickException(
                        f"Required Terraform output '{key}' is missing or empty in deployment state."
                    )
            else:
                unwrapped[key] = str(val)

        return cls(**unwrapped)
