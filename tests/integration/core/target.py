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

from dataclasses import dataclass, field
from enum import StrEnum


class TargetType(StrEnum):
    """Target deployment environment type for integration tests."""

    LOCAL = "local"
    EMULATED = "emulated"
    GCP = "gcp"

    @classmethod
    def from_instance(cls, instance: str | None) -> "TargetType":
        """Resolves an instance name or option string to TargetType enum."""
        if not instance:
            return cls.GCP
        val = instance.strip().lower()
        if val in (cls.LOCAL.value, cls.EMULATED.value):
            return cls.LOCAL
        return cls.GCP

    @property
    def is_local(self) -> bool:
        """Returns True if the target is local / emulated."""
        return self in (TargetType.LOCAL, TargetType.EMULATED)

    @property
    def is_gcp(self) -> bool:
        """Returns True if the target is a live GCP cloud environment."""
        return self == TargetType.GCP


@dataclass
class ArtifactConfig:
    """Configuration for artifact sources and version overrides."""

    cli_source: str = "local"  # "local", "testpypi", "pypi"
    cli_version: str | None = None
    target_tag: str | None = None  # "latest", "dcp-stable", "v1.1.1RC3"
    services_image: str | None = None
    helper_image: str | None = None
    preprocessing_image: str | None = None
    postprocessing_image: str | None = None
    dataflow_template_gcs_path: str | None = None


@dataclass
class DCPTarget:
    """Resolved target environment context for integration testing."""

    project_id: str
    instance_name: str
    workspace_dir: str
    target_type: TargetType = TargetType.GCP
    serving_url: str = ""
    helper_url: str = ""
    spanner_instance: str = ""
    spanner_database: str = ""
    workflow_name: str = ""
    workflow_sa_email: str = ""
    gcs_bucket: str = ""
    artifacts: ArtifactConfig = field(default_factory=ArtifactConfig)

    @property
    def is_local(self) -> bool:
        """Returns True if target is a local emulated stack."""
        return self.target_type.is_local

    @property
    def is_gcp(self) -> bool:
        """Returns True if target is a live GCP cloud environment."""
        return self.target_type.is_gcp
