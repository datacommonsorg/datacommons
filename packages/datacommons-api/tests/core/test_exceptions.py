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

"""Tests for custom exceptions."""

from datacommons_api.core.exceptions import (
    DataCommonsAPIError,
    APIKeyUnauthorizedError,
    APIKeyForbiddenError,
)


def test_exceptions_hierarchy():
    # Verify inheritance
    assert issubclass(APIKeyUnauthorizedError, DataCommonsAPIError)
    assert issubclass(APIKeyForbiddenError, DataCommonsAPIError)
    assert issubclass(DataCommonsAPIError, Exception)


def test_raise_exceptions():
    try:
        raise APIKeyUnauthorizedError("unauthorized")
    except APIKeyUnauthorizedError as e:
        assert str(e) == "unauthorized"

    try:
        raise APIKeyForbiddenError("forbidden")
    except APIKeyForbiddenError as e:
        assert str(e) == "forbidden"
