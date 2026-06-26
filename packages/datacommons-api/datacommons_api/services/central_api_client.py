# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Client wrapper for the central Data Commons API."""

import requests
from datacommons_api.core.exceptions import (
    APIKeyUnauthorizedError,
    APIKeyForbiddenError,
)


class CentralAPIClient:
    """Client for querying the central Data Commons API."""

    def __init__(self, api_key: str, base_url: str = "https://api.datacommons.org"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()

    def query_usa_population(self, timeout: float = 3.0) -> dict:
        """Perform a lightweight USA population query to validate the key."""
        url = f"{self.base_url}/v2/observation"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
        }
        payload = {
            "entity": {"dcids": ["country/USA"]},
            "variable": {"dcids": ["Count_Person"]},
            "date": "latest",
        }

        # Make the request passing the key securely via header.
        response = self.session.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

        if response.status_code == 401:
            raise APIKeyUnauthorizedError("Invalid or expired API key.")
        if response.status_code == 403:
            raise APIKeyForbiddenError("API key lacks permissions or is forbidden.")

        response.raise_for_status()
        return response.json()
