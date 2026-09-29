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

"""Unit tests for datacommons_db.migrations.emulator utilities."""

from unittest.mock import MagicMock, patch

import pytest
from datacommons_db.migrations.emulator import (
    DEFAULT_EMULATOR_HOST,
    ensure_emulator_running,
    ephemeral_emulator_database,
    is_emulator_reachable,
)


def test_is_emulator_reachable_socket_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies is_emulator_reachable returns False on socket error."""
    with patch("socket.create_connection", side_effect=OSError("Connection refused")):
        assert not is_emulator_reachable("localhost:9999")


def test_is_emulator_reachable_success() -> None:
    """Verifies is_emulator_reachable returns True when connection succeeds."""
    mock_sock = MagicMock()
    with patch("socket.create_connection", return_value=mock_sock):
        assert is_emulator_reachable("localhost:9010")
        mock_sock.close.assert_called_once()


def test_ensure_emulator_running_uses_running() -> None:
    """Verifies ensure_emulator_running returns host if reachable."""
    with patch(
        "datacommons_db.migrations.emulator.is_emulator_reachable",
        return_value=True,
    ):
        host = ensure_emulator_running()
        assert host == DEFAULT_EMULATOR_HOST


def test_ensure_emulator_running_no_docker_raises() -> None:
    """Verifies ensure_emulator_running raises ConnectionError if docker not on PATH."""
    with (
        patch(
            "datacommons_db.migrations.emulator.is_emulator_reachable",
            return_value=False,
        ),
        patch("shutil.which", return_value=None),
        pytest.raises(ConnectionError, match="Docker was not found on PATH"),
    ):
        ensure_emulator_running()


def test_ephemeral_emulator_database_lifecycle() -> None:
    """Verifies ephemeral_emulator_database creates instance, creates db, and drops db."""
    mock_instance = MagicMock()
    mock_instance.exists.return_value = True
    mock_db = MagicMock()
    mock_instance.database.return_value = mock_db

    mock_client = MagicMock()
    mock_client.instance.return_value = mock_instance
    mock_client.list_instance_configs.return_value = [
        MagicMock(name="projects/default/instanceConfigs/default")
    ]

    with (
        patch(
            "datacommons_db.migrations.emulator.ensure_emulator_running",
            return_value="localhost:9010",
        ),
        patch(
            "datacommons_db.migrations.emulator.spanner.Client",
            return_value=mock_client,
        ),
    ):
        with ephemeral_emulator_database(project_id="default") as (client, db, sp_client):
            assert client is mock_client
            assert db is mock_db
            assert sp_client.database_id.startswith("snap-")
            mock_db.create().result.assert_called_once()
            mock_db.drop.assert_not_called()

        mock_db.drop.assert_called_once()
