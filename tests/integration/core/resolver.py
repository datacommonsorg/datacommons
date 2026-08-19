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

import json
import subprocess
from pathlib import Path
from typing import Any

from tests.integration.core.target import ArtifactConfig, DCPTarget


def _get_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_terraform_outputs(workspace_dir: Path) -> dict[str, Any]:
    """Reads structured outputs from a Terraform workspace."""
    if (
        not (workspace_dir / ".terraform").exists()
        and not (workspace_dir / "terraform.tfstate").exists()
    ):
        return {}
    try:
        proc = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=str(workspace_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(proc.stdout)
        return {k: v.get("value") for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _find_container_images(data: Any) -> list[str]:
    """Recursively extracts container image URIs from nested resource attributes."""
    images = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "image" and isinstance(v, str) and "/" in v:
                images.append(v)
            elif isinstance(v, (dict, list)):
                images.extend(_find_container_images(v))
    elif isinstance(data, list):
        for item in data:
            images.extend(_find_container_images(item))
    return images


def _extract_images_from_terraform_state(workspace_dir: Path) -> dict[str, str]:
    """Extracts live deployed container images from Terraform state."""
    state_data = None

    # Try local state file first
    tfstate_file = workspace_dir / "terraform.tfstate"
    if tfstate_file.exists():
        try:
            with open(tfstate_file, encoding="utf-8") as f:
                state_data = json.load(f)
        except Exception:
            pass

    # If no local state file, pull from remote backend
    if not state_data and (workspace_dir / ".terraform").exists():
        try:
            proc = subprocess.run(
                ["terraform", "state", "pull"],
                cwd=str(workspace_dir),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout:
                state_data = json.loads(proc.stdout)
        except Exception:
            pass

    images: dict[str, str] = {}
    if not state_data or not isinstance(state_data, dict):
        return images

    for resource in state_data.get("resources", []):
        rname = resource.get("name", "")
        found = _find_container_images(resource.get("instances", []))
        if rname and found:
            images[rname] = found[0]

    return images


def _resolve_deployed_artifacts(
    workspace_dir: Path, artifacts: ArtifactConfig | None = None
) -> ArtifactConfig:
    """Extracts the exact deployed image versions and templates from Terraform state."""
    artifacts = artifacts or ArtifactConfig()
    state_images = _extract_images_from_terraform_state(workspace_dir)

    required_resources = {
        "services_image": "dc_web_service",
        "helper_image": "ingestion_helper",
        "preprocessing_image": "dc_data_job",
        "postprocessing_image": "dc_postprocessing_job",
    }

    resolved = {}
    missing = []
    for field_name, resource_name in required_resources.items():
        img = state_images.get(resource_name)
        if not img:
            missing.append(resource_name)
        else:
            resolved[field_name] = img

    if missing:
        raise RuntimeError(
            f"❌ Error: Could not find deployed container images for {missing} in Terraform state at '{workspace_dir}'."
        )

    services_img = resolved["services_image"]
    dcp_version = services_img.split(":")[-1] if ":" in services_img else "unknown"

    return ArtifactConfig(
        cli_source=artifacts.cli_source,
        cli_version=artifacts.cli_version,
        target_tag=dcp_version,
        services_image=resolved["services_image"],
        helper_image=resolved["helper_image"],
        preprocessing_image=resolved["preprocessing_image"],
        postprocessing_image=resolved["postprocessing_image"],
        dataflow_template_gcs_path=f"gs://datcom-templates/templates/flex/ingestion-{dcp_version}.json",
    )


def resolve_dcp_target(
    instance: str | None = None,
    project: str = "datcom-dcp",
    workspace: str | None = None,
    artifacts: ArtifactConfig | None = None,
) -> DCPTarget:
    """Resolves the active DCP target environment and endpoints."""
    repo_root = _get_repo_root()
    artifacts = artifacts or ArtifactConfig()

    # 1. Resolve Workspace Directory
    if workspace:
        workspace_path = Path(workspace).resolve()
        instance_name = instance or workspace_path.name
    elif instance:
        instance_name = instance
        workspace_path = repo_root / "tests" / "testbed" / "workspaces" / instance
    else:
        curr_dir = Path.cwd().resolve()
        if "workspaces" in str(curr_dir):
            workspace_path = curr_dir
            instance_name = curr_dir.name
        else:
            raise ValueError(
                "❌ Error: Target instance is required.\n"
                "Please specify --instance=<name> (e.g. --instance=testbed-1) or --workspace=<path>."
            )

    # Auto-initialize workspace via connect.sh if missing
    if not workspace_path.exists() or not (workspace_path / ".terraform").exists():
        print(
            f"\n==> [Resolver] Workspace '{workspace_path}' not initialized. Running connect.sh for '{instance_name}'..."
        )
        connect_script = repo_root / "tests" / "testbed" / "connect.sh"
        if connect_script.exists():
            subprocess.run(
                [
                    str(connect_script),
                    "connect",
                    "--instance",
                    instance_name,
                    "--project",
                    project,
                    "--no-shell",
                ],
                check=False,
            )

    # 2. Extract endpoints from Terraform Workspace Outputs
    tf_outputs = _read_terraform_outputs(workspace_path)
    serving_url = tf_outputs.get("datacommons_service_url", "")
    if not serving_url:
        raise RuntimeError(
            f"\n❌ Error: Terraform workspace '{workspace_path}' is not connected or missing required output 'datacommons_service_url'.\n"
            f"Please connect to the target testbed workspace by running:\n"
            f"  tests/testbed/connect.sh connect --instance {instance_name} --project {project}\n"
        )

    if not serving_url.startswith("http"):
        serving_url = f"https://{serving_url}"

    helper_url = tf_outputs.get("ingestion_service_url", "")
    if helper_url and not helper_url.startswith("http"):
        helper_url = f"https://{helper_url}"

    spanner_instance = tf_outputs.get("spanner_instance_id", "")
    spanner_database = tf_outputs.get("spanner_database_id", "dcp_db")
    workflow_name = tf_outputs.get(
        "ingestion_workflow_name", f"{instance_name}-dc-ingestion-workflow"
    )
    workflow_sa = tf_outputs.get("ingestion_workflow_service_account_email", "")
    gcs_bucket = tf_outputs.get("storage_artifacts_bucket_name", "")

    # Resolve deployed container images and template artifacts
    resolved_artifacts = _resolve_deployed_artifacts(workspace_path, artifacts)

    return DCPTarget(
        project_id=project,
        instance_name=instance_name,
        workspace_dir=str(workspace_path),
        serving_url=serving_url,
        helper_url=helper_url,
        spanner_instance=spanner_instance,
        spanner_database=spanner_database,
        workflow_name=workflow_name,
        workflow_sa_email=workflow_sa,
        gcs_bucket=gcs_bucket,
        artifacts=resolved_artifacts,
    )
