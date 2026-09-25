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

"""End-to-end integration tests for init-db and migrate-db workflows on Spanner."""

import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from datacommons_admin.admin_cli import admin
from datacommons_db.clients import SpannerClient


def _is_emulator_available() -> bool:
    """Checks if a Spanner emulator host is configured and reachable."""
    host = os.getenv("SPANNER_EMULATOR_HOST")
    if not host:
        return False
    import socket

    try:
        parts = host.split(":")
        ip = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 9010
        sock = socket.create_connection((ip, port), timeout=1)
        sock.close()
        return True
    except (OSError, ValueError):
        return False


@pytest.mark.skipif(
    not _is_emulator_available(),
    reason="Requires active SPANNER_EMULATOR_HOST (e.g., localhost:9010)",
)
def test_e2e_init_and_migrate_db_on_spanner_emulator(runner: CliRunner):
    """Executes full init-db and migrate-db flows against a live Spanner emulator instance."""
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import spanner

    project_id = "test-project"
    instance_id = "test-instance"
    database_id = "test-e2e-db"

    # Ensure Spanner instance and database exist in emulator
    client = spanner.Client(project=project_id, credentials=AnonymousCredentials())
    instance = client.instance(instance_id)
    if not instance.exists():
        instance.create().result(timeout=10)
    db = instance.database(database_id)
    if not db.exists():
        db.create().result(timeout=10)

    spanner_client = SpannerClient(
        project_id=project_id,
        instance_id=instance_id,
        database_id=database_id,
        credentials=AnonymousCredentials(),
    )

    with patch("datacommons_admin.db.db_cli._setup_spanner_client") as mock_setup:
        mock_setup.return_value = spanner_client

        # 1. First init-db on fresh DB
        init_res = runner.invoke(admin, ["init-db"])
        assert init_res.exit_code == 0, f"init-db failed: {init_res.output}"
        assert "Applied baseline schema (schema.sql)" in init_res.output
        assert "Successfully initialized Spanner database!" in init_res.output

        # Verify tables exist on emulator
        assert spanner_client.table_exists("Node")
        assert spanner_client.table_exists("Edge")
        assert spanner_client.table_exists("SchemaMigrations")

        # 2. Re-running init-db should be rejected with friendly message
        reinit_res = runner.invoke(admin, ["init-db"])
        assert reinit_res.exit_code != 0
        assert "is already initialized" in reinit_res.output
        assert "run 'datacommons admin migrate-db'" in reinit_res.output

        # 3. Running migrate-db should detect up-to-date schema
        mig_res = runner.invoke(admin, ["migrate-db", "-y"])
        assert mig_res.exit_code == 0
        assert "Database schema is already up-to-date" in mig_res.output
