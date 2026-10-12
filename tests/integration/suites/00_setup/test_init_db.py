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

"""Integration tests validating Data Commons database setup and schema initialization via CLI."""

import pytest

from tests.integration.core.cli_runner import DatacommonsCLI
from tests.integration.core.config_schema import TestManifest


class TestDBSetup:
    """Validates Data Commons database initialization and schema migration commands."""

    def test_01_cli_init_db(
        self,
        request,
        dcp_cli: DatacommonsCLI,
        test_manifest: TestManifest,
    ):
        """Validates that 'datacommons admin init-db' initializes the Spanner database and schema."""
        if request.config.getoption("--reuse-data"):
            pytest.skip(
                "Skipped Spanner database initialization because --reuse-data was specified."
            )

        # Allow up to 600s for dynamic git package build, dependency resolution, lock acquisition,
        # and Spanner DDL migrations.
        res = dcp_cli.run(["admin", "init-db"], timeout=600)
        assert res.exit_code == 0, f"CLI init-db failed: {res.output}"
        assert (
            "Successfully initialized Spanner database!" in res.output
            or "is already initialized" in res.output
        )
