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
import re
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
            timeout=30,
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


def _load_terraform_state(workspace_dir: Path) -> dict | None:
    """Loads local terraform.tfstate or pulls from remote backend."""
    tfstate_file = workspace_dir / "terraform.tfstate"
    if tfstate_file.exists():
        try:
            with open(tfstate_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    if (workspace_dir / ".terraform").exists():
        proc = subprocess.run(
            ["terraform", "state", "pull"],
            cwd=str(workspace_dir),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            try:
                return json.loads(proc.stdout)
            except Exception:
                pass
    return None


def _resolve_deployed_artifacts(
    workspace_dir: Path, artifacts: ArtifactConfig | None = None
) -> ArtifactConfig:
    """Extracts exact deployed container image digests and Dataflow templates from Terraform state."""
    artifacts = artifacts or ArtifactConfig()
    state_data = _load_terraform_state(workspace_dir) or {}

    resource_map = {
        "dc_web_service": "services_image",
        "ingestion_helper": "helper_image",
        "dc_data_job": "preprocessing_image",
        "dc_postprocessing_job": "postprocessing_image",
    }

    resolved = {}
    template_path = None

    # Inspect exact resource names from Terraform state
    for resource in state_data.get("resources", []):
        rname = resource.get("name", "")
        instances = resource.get("instances", [])
        if not instances:
            continue

        attrs = instances[0].get("attributes", {})

        # Extract container images for Cloud Run services and jobs
        if rname in resource_map:
            imgs = _find_container_images(instances)
            if imgs:
                resolved[resource_map[rname]] = imgs[0]

        # Extract Dataflow template GCS path from Workflow source_contents
        if rname == "ingestion_orchestrator":
            source = attrs.get("source_contents", "")
            match = re.search(
                r"['\"]?containerSpecGcsPath['\"]?\s*:\s*['\"]?(gs://[^\s'\"\\,]+\.json)['\"]?",
                source,
            )
            if match:
                template_path = match.group(1)

    missing = [field for field in resource_map.values() if field not in resolved]
    if missing or not template_path:
        raise RuntimeError(
            f"❌ Error: Could not find deployed artifacts for missing fields in Terraform state at '{workspace_dir}': "
            f"missing_images={missing}, missing_template={template_path is None}."
        )

    raw_artifacts = {
        **resolved,
        "dataflow_template_gcs_path": template_path,
    }

    digests = _resolve_artifact_digests(raw_artifacts)

    return ArtifactConfig(
        cli_source=artifacts.cli_source,
        cli_version=artifacts.cli_version,
        target_tag=artifacts.target_tag or "latest",
        services_image=digests["services_image"],
        helper_image=digests["helper_image"],
        preprocessing_image=digests["preprocessing_image"],
        postprocessing_image=digests["postprocessing_image"],
        dataflow_template_gcs_path=digests["dataflow_template_gcs_path"],
    )


def _resolve_image_digest(uri: str) -> str:
    if "@sha256:" in uri:
        return uri
    cmd = (
        [
            "gcloud",
            "container",
            "images",
            "describe",
            uri,
            "--format=value(image_summary.digest)",
        ]
        if "gcr.io/" in uri
        else [
            "gcloud",
            "artifacts",
            "docker",
            "images",
            "describe",
            uri,
            "--format=value(image_summary.digest)",
        ]
    )
    digest = _exec_cmd(cmd)
    base = uri.split("@")[0]
    if ":" in base:
        last_slash = base.rfind("/")
        last_colon = base.rfind(":")
        if last_colon > last_slash:
            base = base[:last_colon]
    return f"{base}@{digest}" if digest and digest.startswith("sha256:") else uri


def _resolve_gcs_generation(uri: str) -> str:
    if "#" in uri:
        return uri
    gen = _exec_cmd(
        [
            "gcloud",
            "storage",
            "objects",
            "describe",
            uri,
            "--format=value(generation)",
        ]
    )
    return f"{uri}#{gen}" if gen and gen.isdigit() else uri


def _resolve_artifact_digests(artifacts: dict[str, str]) -> dict[str, str]:
    """Resolves container image tags to sha256 digests and GCS paths to generation IDs."""
    resolved = {}
    for key, val in artifacts.items():
        if not isinstance(val, str):
            resolved[key] = val
        elif "gcr.io/" in val or "pkg.dev/" in val:
            resolved[key] = _resolve_image_digest(val)
        elif val.startswith("gs://"):
            resolved[key] = _resolve_gcs_generation(val)
        else:
            resolved[key] = val
    return resolved


def _exec_cmd(cmd: list[str], timeout: int = 5) -> str:
    try:
        return (
            subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=timeout)
            .decode()
            .strip()
        )
    except Exception:
        return ""


def resolve_dcp_target(
    instance: str | None = None,
    project: str = "datcom-dcp",
    workspace: str | None = None,
    artifacts: ArtifactConfig | None = None,
) -> DCPTarget:
    """Resolves the active DCP target environment and endpoints."""
    repo_root = _get_repo_root()
    artifacts = artifacts or ArtifactConfig()

    # 1. Resolve Emulated vs Cloud Workspace Directory
    if instance == "emulated":
        return DCPTarget(
            project_id="default",
            instance_name="emulated",
            workspace_dir=str(repo_root / "tests" / "integration" / "emulated"),
            serving_url="http://localhost:8082",
            helper_url="http://localhost:8081",
            spanner_instance="default",
            spanner_database="test-db",
            workflow_name="local-workflow",
            workflow_sa_email="local-sa@default.iam.gserviceaccount.com",
            gcs_bucket="test-bucket",
            artifacts=artifacts,
        )

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

    # Auto-initialize workspace via fetch_terraform_state.sh if missing
    if not workspace_path.exists() or not (workspace_path / ".terraform").exists():
        print(
            f"\n==> [Resolver] Workspace '{workspace_path}' not initialized. Running fetch_terraform_state.sh for '{instance_name}'..."
        )
        fetch_script = repo_root / "tests" / "testbed" / "fetch_terraform_state.sh"
        if fetch_script.exists():
            subprocess.run(
                [
                    str(fetch_script),
                    "connect",
                    "--instance",
                    instance_name,
                    "--project",
                    project,
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
            f"  tests/testbed/fetch_terraform_state.sh connect --instance {instance_name} --project {project}\n"
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
