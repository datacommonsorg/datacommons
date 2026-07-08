# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Monkeypatch to allow Spanner client libraries to connect to emulators.

This acts as a temporary workaround. The long-term fix should be implemented in
the ingestion helper service (inside the import repository).
"""

import os
import sys

import google.cloud.spanner_admin_database_v1
import grpc
from google.auth.credentials import AnonymousCredentials
from google.cloud import spanner
from google.cloud.spanner_admin_database_v1 import DatabaseAdminClient
from google.cloud.spanner_admin_database_v1.services.database_admin.transports.grpc import (
    DatabaseAdminGrpcTransport,
)

# Avoid attribute errors on AnonymousCredentials
AnonymousCredentials.with_quota_project = lambda self, *args, **kwargs: self

original_spanner_init = spanner.Client.__init__


def patched_spanner_init(self, *args, **kwargs):
    emulator_host = os.getenv("SPANNER_EMULATOR_HOST")
    if emulator_host:
        kwargs["credentials"] = AnonymousCredentials()
    original_spanner_init(self, *args, **kwargs)


spanner.Client.__init__ = patched_spanner_init


class InsecureDatabaseAdminClient(DatabaseAdminClient):
    def __init__(self, *args, **kwargs):
        emulator_host = os.getenv("SPANNER_EMULATOR_HOST")
        if emulator_host:
            channel = grpc.insecure_channel(emulator_host)
            kwargs["transport"] = DatabaseAdminGrpcTransport(
                channel=channel, credentials=AnonymousCredentials()
            )
            if "credentials" in kwargs:
                del kwargs["credentials"]
        super().__init__(*args, **kwargs)

    def update_database_ddl(self, request=None, *args, **kwargs):
        emulator_host = os.getenv("SPANNER_EMULATOR_HOST")
        if emulator_host:
            req_obj = request if request is not None else kwargs.get("request")
            if req_obj is not None:
                if hasattr(req_obj, "statements"):
                    filtered_statements = []
                    for stmt in req_obj.statements:
                        normalized = stmt.strip().upper()
                        if normalized.startswith(
                            ("CREATE MODEL", "CREATE VECTOR INDEX")
                        ):
                            continue
                        filtered_statements.append(stmt)
                    del req_obj.statements[:]
                    req_obj.statements.extend(filtered_statements)
                elif isinstance(req_obj, dict) and "statements" in req_obj:
                    req_obj["statements"] = [
                        s
                        for s in req_obj["statements"]
                        if not s.strip()
                        .upper()
                        .startswith(("CREATE MODEL", "CREATE VECTOR INDEX"))
                    ]
            elif "statements" in kwargs:
                kwargs["statements"] = [
                    s
                    for s in kwargs["statements"]
                    if not s.strip()
                    .upper()
                    .startswith(("CREATE MODEL", "CREATE VECTOR INDEX"))
                ]
        return super().update_database_ddl(request, *args, **kwargs)


google.cloud.spanner_admin_database_v1.DatabaseAdminClient = InsecureDatabaseAdminClient

if "clients.spanner" in sys.modules:
    sys.modules["clients.spanner"].DatabaseAdminClient = InsecureDatabaseAdminClient

__version__ = "0.0.0-dev"
