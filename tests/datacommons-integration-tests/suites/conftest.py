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
import urllib.request

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--target-url",
        action="store",
        default="http://localhost:8080",
        help="Target base URL of the Data Commons serving services instance under test",
    )


@pytest.fixture(scope="session")
def target_url(request):
    return request.config.getoption("--target-url").rstrip("/")


@pytest.fixture(scope="session")
def api_client():
    def _make_request(
        target_url: str, path: str, headers: dict = None, *, is_json: bool = True
    ):
        url = f"{target_url}{path}"
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"URL scheme must be http or https, got: {url}")
        req = urllib.request.Request(url)  # noqa: S310
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=15) as response:  # noqa: S310
                status_code = response.getcode()
                if status_code != 200:
                    raise AssertionError(
                        f"Expected HTTP status code 200, got: {status_code}"
                    )
                body = response.read().decode("utf-8")
                if is_json:
                    try:
                        return json.loads(body)
                    except json.JSONDecodeError as jde:
                        raise AssertionError(
                            f"Response body is not valid JSON: {jde}. Raw body snippet (first 500 chars): {body[:500]}"
                        ) from jde
                return body
        except Exception as e:  # noqa: BLE001
            raise AssertionError(f"HTTP request to {url} failed: {e}") from e

    return _make_request
