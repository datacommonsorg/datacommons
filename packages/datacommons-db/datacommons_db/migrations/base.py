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

from abc import ABC, abstractmethod

from datacommons_db.clients.spanner_client import SpannerClient


class SchemaMigration(ABC):
    """Base class for defining Spanner schema migration scripts."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of this schema migration."""

    @property
    @abstractmethod
    def creation_timestamp(self) -> str:
        """UTC ISO-8601 creation timestamp (e.g. '2026-08-17T15:30:00Z')."""

    @abstractmethod
    def upgrade(self, spanner_client: SpannerClient) -> None:
        """Executes forward schema changes to upgrade the database.

        Args:
            spanner_client: SpannerClient instance to execute DDL / DML.

        Raises:
            RuntimeError: If any DDL or DML operation fails.
        """
