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

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datacommons_db.clients.spanner_client import SpannerClient


def inspect_database_schema(spanner_client: SpannerClient) -> list[str]:
    """Retrieves engine-materialized DDL statements from the active Cloud Spanner database or emulator.

    Uses the Spanner admin API `database_admin_api.get_database_ddl()` to inspect the live collapsed schema.

    Args:
        spanner_client: Connected SpannerClient instance.

    Returns:
        List of DDL statement strings representing the live database schema.
    """
    database_name = spanner_client.database.name
    response = spanner_client.client.database_admin_api.get_database_ddl(
        database=database_name
    )
    return list(response.statements)
