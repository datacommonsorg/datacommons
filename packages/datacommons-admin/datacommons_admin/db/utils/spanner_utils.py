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
from datacommons_db.clients import SpannerClient


def _create_spanner_client(
    project_id: str, instance_id: str, database_id: str
) -> SpannerClient:
    """Initializes and returns a SpannerClient instance.

    Args:
        project_id: GCP project ID hosting the Spanner database.
        instance_id: Cloud Spanner instance ID.
        database_id: Cloud Spanner database ID.

    Returns:
        A configured SpannerClient instance.

    Raises:
        click.ClickException: If initialization of the SpannerClient fails.
    """
    try:
        return SpannerClient(
            project_id=project_id,
            instance_id=instance_id,
            database_id=database_id,
        )
    except Exception as e:
        raise click.ClickException(f"Failed to initialize Spanner client: {e}") from e


def check_database_exists(
    project_id: str, instance_id: str, database_id: str
) -> bool:
    """Checks whether the Cloud Spanner database exists.

    Args:
        project_id: GCP project ID hosting the Spanner database.
        instance_id: Cloud Spanner instance ID.
        database_id: Cloud Spanner database ID.

    Returns:
        True if the database exists, False otherwise.
    """
    try:
        spanner_client = _create_spanner_client(
            project_id=project_id,
            instance_id=instance_id,
            database_id=database_id,
        )
        return spanner_client.database_exists()
    except Exception:  # noqa: BLE001 - must catch all exceptions to safely detect existence
        return False
