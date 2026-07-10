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
import click
import google.auth
from google.auth.transport.requests import AuthorizedSession


class IngestionJobClient:
    """Client for interacting with Cloud Workflows and Cloud Run Admin APIs to manage CDC data ingestion."""

    def __init__(
        self,
        job_name: str,
        workflow_name: str = None,
        service_account_email: str = None,
        project_id: str = None,
        location: str = None,
    ) -> None:
        self.service_account_email = service_account_email
        self.project_id = project_id
        self.location = location
        base_credentials, _ = google.auth.default()

        need_project_and_location = (
            (workflow_name and not workflow_name.startswith("projects/")) or
            (job_name and not job_name.startswith("projects/"))
        )
        if need_project_and_location:
            if not project_id:
                raise click.ClickException(
                    "Project ID must be provided via Terraform outputs or as an argument."
                )
            if not location:
                raise click.ClickException(
                    "Location must be provided via Terraform outputs or as an argument."
                )

        if workflow_name:
            if not workflow_name.startswith("projects/"):
                self.full_workflow_name = (
                    f"projects/{project_id}/locations/{location}/workflows/{workflow_name}"
                )
            else:
                self.full_workflow_name = workflow_name
        else:
            self.full_workflow_name = None

        if not job_name.startswith("projects/"):
            self.full_job_name = (
                f"projects/{project_id}/locations/{location}/jobs/{job_name}"
            )
        else:
            self.full_job_name = job_name

        if service_account_email:
            from google.auth import impersonated_credentials

            creds = impersonated_credentials.Credentials(
                source_credentials=base_credentials,
                target_principal=service_account_email,
                target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        else:
            creds = base_credentials

        self.session = AuthorizedSession(creds)

    def start_workflow(self, imports: str | None = None) -> dict:
        """Starts an execution of the Cloud Workflow."""
        if not self.full_workflow_name:
            raise click.ClickException(
                "Workflow name must be provided to start a workflow execution."
            )

        # 1. Fetch Cloud Run job configuration to get default bucket, region, etc.
        env_vars = self.get_config()
        env_dict = {env["name"]: env.get("value") for env in env_vars if "name" in env}

        temp_location = env_dict.get("TEMP_LOCATION")
        spanner_instance = env_dict.get("GCP_SPANNER_INSTANCE_ID")
        spanner_database = env_dict.get("GCP_SPANNER_DATABASE_NAME")
        region = env_dict.get("REGION", self.location)

        if not temp_location:
            raise click.ClickException(
                "TEMP_LOCATION not found in preprocessing job environment configuration."
            )

        # 2. Parse imports argument
        imports_list = []
        if imports:
            imports_list = [imp.strip() for imp in imports.split(",") if imp.strip()]

        # 3. Construct payload argument (must be a JSON string)
        argument_dict = {
            "tempLocation": temp_location,
            "spannerInstanceId": spanner_instance or "",
            "spannerDatabaseId": spanner_database or "",
            "region": region,
            "imports": imports_list
        }

        url = f"https://workflowexecutions.googleapis.com/v1/{self.full_workflow_name}/executions"
        json_payload = {
            "argument": json.dumps(argument_dict)
        }

        try:
            response = self.session.post(url, json=json_payload, timeout=300)
        except Exception as e:
            msg = f"Network or authentication error connecting to Workflow Executions API at {url}: {e}"
            if self.service_account_email:
                msg += f"\nFailed to impersonate {self.service_account_email}. Please ensure your GCP user account has the 'Service Account Token Creator' (roles/iam.serviceAccountTokenCreator) IAM role."
            raise click.ClickException(msg)

        if response.status_code == 401:
            raise click.ClickException(
                f"HTTP 401 Unauthorized when calling Workflow Executions API at {url}.\n"
                "Your GCP credentials were rejected. Please verify your authentication.\n"
                "To re-authenticate, run:\n"
                "  gcloud auth application-default login"
            )

        if not response.ok:
            try:
                error_data = response.json()
                error_msg = (
                    error_data.get("message")
                    or error_data.get("error", {}).get("message")
                    or response.text
                )
            except Exception:
                error_msg = response.text

            raise click.ClickException(
                f"Workflow Executions API returned HTTP {response.status_code}: {error_msg}"
            )

        try:
            return response.json()
        except Exception:
            return {"status": "success", "message": response.text}

    def get_config(self) -> list:
        """Retrieves the environment variables configuration of the Cloud Run job."""
        url = f"https://run.googleapis.com/v2/{self.full_job_name}"
        try:
            response = self.session.get(url, timeout=300)
        except Exception as e:
            msg = f"Network or authentication error connecting to Cloud Run Admin API at {url}: {e}"
            if self.service_account_email:
                msg += f"\nFailed to impersonate {self.service_account_email}. Please ensure your GCP user account has the 'Service Account Token Creator' (roles/iam.serviceAccountTokenCreator) IAM role."
            raise click.ClickException(msg)

        if response.status_code == 401:
            raise click.ClickException(
                f"HTTP 401 Unauthorized when calling Cloud Run Admin API at {url}.\n"
                "Your GCP credentials were rejected. Please verify your authentication.\n"
                "To re-authenticate, run:\n"
                "  gcloud auth application-default login"
            )

        if not response.ok:
            try:
                error_data = response.json()
                error_msg = (
                    error_data.get("message")
                    or error_data.get("error", {}).get("message")
                    or response.text
                )
            except Exception:
                error_msg = response.text

            raise click.ClickException(
                f"Cloud Run Admin API returned HTTP {response.status_code}: {error_msg}"
            )

        try:
            job_data = response.json()
        except Exception as e:
            raise click.ClickException(f"Failed to parse Cloud Run job response: {e}")

        containers = (
            job_data.get("template", {}).get("template", {}).get("containers", [])
        )
        if not containers:
            return []

        return containers[0].get("env", [])
