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

"""Spanner emulator compatibility and DDL filtering patch.

1. Injects AnonymousCredentials when SPANNER_EMULATOR_HOST is set.
2. Filters cloud-only 'CREATE MODEL' and 'CREATE VECTOR INDEX' statements from DDL
   since Spanner Omni does not support Vertex AI ML vector indexing.
"""

import os
import sys

try:
    import google.cloud.spanner_admin_database_v1
    import grpc
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import spanner
    from google.cloud.spanner_admin_database_v1 import DatabaseAdminClient
    from google.cloud.spanner_admin_database_v1.services.database_admin.transports.grpc import (
        DatabaseAdminGrpcTransport,
    )

    HAS_SPANNER = True
except (ImportError, ModuleNotFoundError):
    HAS_SPANNER = False

if HAS_SPANNER:
    # Prevent attribute errors on AnonymousCredentials when SDK calls with_quota_project
    AnonymousCredentials.with_quota_project = lambda self, *args, **kwargs: self

    original_spanner_init = spanner.Client.__init__

    def patched_spanner_init(self, *args, **kwargs):
        if os.getenv("SPANNER_EMULATOR_HOST"):
            kwargs["credentials"] = AnonymousCredentials()
        original_spanner_init(self, *args, **kwargs)

    spanner.Client.__init__ = patched_spanner_init

    _EXCLUDED_DDL_PREFIXES = ("CREATE MODEL", "CREATE VECTOR INDEX")

    def _filter_ddl(statements):
        return [
            s
            for s in statements
            if not s.strip().upper().startswith(_EXCLUDED_DDL_PREFIXES)
        ]

    class InsecureDatabaseAdminClient(DatabaseAdminClient):
        """DatabaseAdminClient using insecure gRPC channel and filtering cloud-only DDL."""

        def __init__(self, *args, **kwargs):
            emulator_host = os.getenv("SPANNER_EMULATOR_HOST")
            if emulator_host:
                channel = grpc.insecure_channel(emulator_host)
                kwargs["transport"] = DatabaseAdminGrpcTransport(
                    channel=channel, credentials=AnonymousCredentials()
                )
                kwargs.pop("credentials", None)
            super().__init__(*args, **kwargs)

        def update_database_ddl(self, request=None, *args, **kwargs):
            """Filters out CREATE MODEL and CREATE VECTOR INDEX statements for emulator."""
            if request and hasattr(request, "statements"):
                request.statements[:] = _filter_ddl(request.statements)
            return super().update_database_ddl(request, *args, **kwargs)

    google.cloud.spanner_admin_database_v1.DatabaseAdminClient = (
        InsecureDatabaseAdminClient
    )
    if "clients.spanner" in sys.modules:
        sys.modules["clients.spanner"].DatabaseAdminClient = InsecureDatabaseAdminClient
