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
import os
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
            check=True,
        )
        data = json.loads(proc.stdout)
        return {k: v.get("value") for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        return {}


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

    for r in state_data.get("resources", []):
        rtype = r.get("type", "")
        rname = r.get("name", "")
        for inst in r.get("instances", []):
            attrs = inst.get("attributes", {})
            # Cloud Run Services v2 (dc_web_service, ingestion_helper)
            if rtype == "google_cloud_run_v2_service":
                for tmpl in attrs.get("template", []):
                    for c in tmpl.get("containers", []):
                        img = c.get("image")
                        if img:
                            images[rname] = img
            # Cloud Run Jobs v2 (dc_data_job, dc_postprocessing_job)
            elif rtype == "google_cloud_run_v2_job":
                for tmpl in attrs.get("template", []):
                    for t2 in tmpl.get("template", []):
                        for c in t2.get("containers", []):
                            img = c.get("image")
                            if img:
                                images[rname] = img

    return images


def _resolve_deployed_artifacts(
    workspace_dir: Path, artifacts: ArtifactConfig | None = None
) -> ArtifactConfig:
    """Extracts the exact deployed image versions and templates from Terraform."""
    artifacts = artifacts or ArtifactConfig()
    tfvars_path = workspace_dir / "terraform.tfvars"

    dcp_version = artifacts.target_tag or "1.1.2"
    services_img = artifacts.services_image
    helper_img = artifacts.helper_image
    prep_img = artifacts.preprocessing_image
    post_img = artifacts.postprocessing_image
    df_template = artifacts.dataflow_template_gcs_path

    # 1. Inspect live Terraform state for exact deployed images
    state_images = _extract_images_from_terraform_state(workspace_dir)
    if "dc_web_service" in state_images and not services_img:
        services_img = state_images["dc_web_service"]
    if "ingestion_helper" in state_images and not helper_img:
        helper_img = state_images["ingestion_helper"]
    if "dc_data_job" in state_images and not prep_img:
        prep_img = state_images["dc_data_job"]
    if "dc_postprocessing_job" in state_images and not post_img:
        post_img = state_images["dc_postprocessing_job"]

    # 2. Check terraform.tfvars overrides
    if tfvars_path.exists():
        try:
            with open(tfvars_path, encoding="utf-8") as f:
                content = f.read()
            for raw_line in content.splitlines():
                line = raw_line.strip()
                if line.startswith("#"):
                    continue
                m_ver = re.match(r'dcp_version\s*=\s*"([^"]+)"', line)
                if m_ver and not artifacts.target_tag:
                    dcp_version = m_ver.group(1)
                m_srv = re.match(r'datacommons_services_image\s*=\s*"([^"]+)"', line)
                if m_srv and not services_img:
                    services_img = m_srv.group(1)
                m_hlp = re.match(
                    r'ingestion_helper_service_image\s*=\s*"([^"]+)"', line
                )
                if m_hlp and not helper_img:
                    helper_img = m_hlp.group(1)
                m_prep = re.match(
                    r'ingestion_preprocessing_job_image\s*=\s*"([^"]+)"', line
                )
                if m_prep and not prep_img:
                    prep_img = m_prep.group(1)
                m_post = re.match(
                    r'ingestion_postprocessing_job_image\s*=\s*"([^"]+)"', line
                )
                if m_post and not post_img:
                    post_img = m_post.group(1)
                m_df = re.match(
                    r'ingestion_dataflow_template_gcs_path\s*=\s*"([^"]+)"', line
                )
                if m_df and not df_template:
                    df_template = m_df.group(1)
        except Exception:
            pass

    # 3. Fallbacks
    services_img = (
        services_img or f"gcr.io/datcom-ci/datacommons-services:{dcp_version}"
    )
    helper_img = (
        helper_img or f"gcr.io/datcom-ci/datacommons-ingestion-helper:{dcp_version}"
    )
    prep_img = prep_img or f"gcr.io/datcom-ci/datacommons-data:{dcp_version}"
    post_img = (
        post_img or f"gcr.io/datcom-ci/datacommons-aggregation-helper:{dcp_version}"
    )
    df_template = (
        df_template
        or f"gs://datcom-templates/templates/flex/ingestion-{dcp_version}.json"
    )

    return ArtifactConfig(
        cli_source=artifacts.cli_source,
        cli_version=artifacts.cli_version,
        target_tag=dcp_version,
        services_image=services_img,
        helper_image=helper_img,
        preprocessing_image=prep_img,
        postprocessing_image=post_img,
        dataflow_template_gcs_path=df_template,
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
            instance_name = os.environ.get("DCP_INSTANCE", "testbed-1")
            workspace_path = (
                repo_root / "tests" / "testbed" / "workspaces" / instance_name
            )

    # Auto-initialize workspace if missing
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

    serving_url = (
        tf_outputs.get("datacommons_service_url")
        or tf_outputs.get("custom_domain")
        or os.environ.get("DCP_SERVING_URL", "")
    )
    if serving_url and not serving_url.startswith("http"):
        serving_url = f"https://{serving_url}"

    helper_url = (
        tf_outputs.get("ingestion_service_url")
        or tf_outputs.get("ingestion_helper_url")
        or os.environ.get("DCP_HELPER_URL", "")
    )
    if helper_url and not helper_url.startswith("http"):
        helper_url = f"https://{helper_url}"

    spanner_instance = tf_outputs.get("spanner_instance_id") or os.environ.get(
        "DCP_SPANNER_INSTANCE", f"dcp-spanner-{instance_name}"
    )

    spanner_database = tf_outputs.get("spanner_database_id") or os.environ.get(
        "DCP_SPANNER_DATABASE", "dcp_db"
    )

    workflow_name = tf_outputs.get("ingestion_workflow_name") or os.environ.get(
        "DCP_WORKFLOW_NAME", f"{instance_name}-dc-ingestion-workflow"
    )

    workflow_sa = tf_outputs.get(
        "ingestion_workflow_service_account_email"
    ) or os.environ.get("DCP_WORKFLOW_SA", "")

    gcs_bucket = (
        tf_outputs.get("storage_artifacts_bucket_name")
        or tf_outputs.get("ingestion_bucket_url")
        or tf_outputs.get("ingestion_bucket")
        or os.environ.get("DCP_GCS_BUCKET", "")
    )

    # Resolve deployed container images and template artifacts
    resolved_artifacts = _resolve_deployed_artifacts(workspace_path, artifacts)

    return DCPTarget(
        project_id=project or os.environ.get("DCP_PROJECT_ID", "datcom-dcp"),
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
