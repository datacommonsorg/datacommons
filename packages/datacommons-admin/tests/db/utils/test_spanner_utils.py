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

from unittest.mock import MagicMock, patch

import click
import pytest
from datacommons_admin.db.utils.spanner_utils import (
    _create_spanner_client,
    check_database_initialized,
)


def test_create_spanner_client_success() -> None:
    with patch(
        "datacommons_admin.db.utils.spanner_utils.SpannerClient"
    ) as mock_spanner_cls:
        mock_client = MagicMock()
        mock_spanner_cls.return_value = mock_client

        client = _create_spanner_client("proj", "inst", "db")
        assert client == mock_client
        mock_spanner_cls.assert_called_once_with(
            project_id="proj", instance_id="inst", database_id="db"
        )


def test_create_spanner_client_failure_raises_click_exception() -> None:
    with (
        patch(
            "datacommons_admin.db.utils.spanner_utils.SpannerClient",
            side_effect=Exception("Initialization error"),
        ),
        pytest.raises(
            click.ClickException, match="Failed to initialize Spanner client"
        ),
    ):
        _create_spanner_client("proj", "inst", "db")


def test_check_database_initialized_true() -> None:
    with patch(
        "datacommons_admin.db.utils.spanner_utils._create_spanner_client"
    ) as mock_factory:
        mock_client = MagicMock()
        mock_client.table_exists.return_value = True
        mock_factory.return_value = mock_client

        assert check_database_initialized("proj", "inst", "db") is True
        mock_factory.assert_called_once_with(
            project_id="proj", instance_id="inst", database_id="db"
        )
        mock_client.table_exists.assert_called_once_with("Node")


def test_check_database_initialized_false() -> None:
    with patch(
        "datacommons_admin.db.utils.spanner_utils._create_spanner_client"
    ) as mock_factory:
        mock_client = MagicMock()
        mock_client.table_exists.return_value = False
        mock_factory.return_value = mock_client

        assert check_database_initialized("proj", "inst", "db") is False
        mock_factory.assert_called_once_with(
            project_id="proj", instance_id="inst", database_id="db"
        )
        mock_client.table_exists.assert_called_once_with("Node")


def test_check_database_initialized_exception_returns_false() -> None:
    with patch(
        "datacommons_admin.db.utils.spanner_utils._create_spanner_client",
        side_effect=Exception("Connection error"),
    ):
        assert check_database_initialized("proj", "inst", "db") is False
