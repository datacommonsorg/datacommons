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

import click
import google.auth
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import id_token


class IngestionHelperClient:
    """Client for interacting with the DCP Ingestion Helper Cloud Run service."""

    def __init__(self, base_url: str, service_account_email: str = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_req = Request()
        self.service_account_email = service_account_email

        base_credentials, _ = google.auth.default()

        if service_account_email:
            from google.auth import impersonated_credentials

            target_credentials = impersonated_credentials.Credentials(
                source_credentials=base_credentials,
                target_principal=service_account_email,
                target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            creds = impersonated_credentials.IDTokenCredentials(
                target_credentials=target_credentials,
                target_audience=self.base_url,
                include_email=True,
            )
        else:
            try:
                token = id_token.fetch_id_token(self.auth_req, self.base_url)
                from google.oauth2.credentials import Credentials

                creds = Credentials(token)
            except Exception as e:
                raise click.ClickException(
                    f"Failed to fetch ID token for {self.base_url}: {e}\n"
                    "Please ensure you are authenticated or provide a service account to impersonate."
                )

        self.session = AuthorizedSession(creds)

    def _call_endpoint(self, path: str, payload: dict = None) -> dict:
        if payload is None:
            payload = {}
        url = f"{self.base_url}/{path.lstrip('/')}"

        try:
            response = self.session.post(url, json=payload, timeout=300)
        except Exception as e:
            msg = f"Network or authentication error connecting to Ingestion Helper service at {url}: {e}"
            if self.service_account_email:
                msg += f"\nFailed to impersonate {self.service_account_email}. Please ensure your GCP user account has the 'Service Account Token Creator' (roles/iam.serviceAccountTokenCreator) IAM role."
            raise click.ClickException(msg)

        if response.status_code == 401:
            raise click.ClickException(
                f"HTTP 401 Unauthorized when calling Ingestion Helper at {url}.\n"
                "Your GCP credentials were rejected. Please verify that the service account has the 'Cloud Run Invoker' (roles/run.invoker) IAM role for this service.\n"
                "To re-authenticate, run:\n"
                "  gcloud auth application-default login"
            )

        if not response.ok:
            try:
                error_data = response.json()
                detail = error_data.get("detail")
                if isinstance(detail, list):
                    error_msg = ", ".join(
                        [
                            f"{'.'.join(str(loc) for loc in err.get('loc', []))}: {err.get('msg')}"
                            for err in detail
                            if isinstance(err, dict)
                        ]
                    ) or str(detail)
                else:
                    error_msg = (
                        error_data.get("message")
                        or (str(detail) if detail is not None else None)
                        or error_data.get("error")
                        or response.text
                    )
            except Exception:
                error_msg = response.text

            raise click.ClickException(
                f"Ingestion Helper returned HTTP {response.status_code}: {error_msg}"
            )

        try:
            return response.json()
        except Exception:
            return {"status": "success", "message": response.text}

    def initialize_database(self) -> dict:
        """Calls the initialize_database endpoint on the ingestion helper service."""
        return self._call_endpoint("database/initialize")

    def seed_database(self) -> dict:
        """Calls the seed_database endpoint on the ingestion helper service."""
        return self._call_endpoint("database/seed")
