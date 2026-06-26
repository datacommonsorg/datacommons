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

"""Custom exceptions for the Data Commons API."""


class DataCommonsAPIError(Exception):
    """Base exception for all Data Commons API errors."""

    pass


class APIKeyUnauthorizedError(DataCommonsAPIError):
    """Raised when the configured DC_API_KEY is invalid or expired (HTTP 401)."""

    pass


class APIKeyForbiddenError(DataCommonsAPIError):
    """Raised when the configured DC_API_KEY lacks permissions (HTTP 403)."""

    pass
