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

# =========================================================================
# TEMPORARY SPANNER EMULATOR PATCH BLOCK START
# TODO(cleanup): Delete this entire Spanner patch block once the import
# repository PR for Spanner emulator support is merged and released.
# =========================================================================
try:
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

    google.cloud.spanner_admin_database_v1.DatabaseAdminClient = (
        InsecureDatabaseAdminClient
    )

    if "clients.spanner" in sys.modules:
        sys.modules["clients.spanner"].DatabaseAdminClient = InsecureDatabaseAdminClient
except ModuleNotFoundError:
    pass
# =========================================================================
# TEMPORARY SPANNER EMULATOR PATCH BLOCK END
# =========================================================================

try:
    import fs_gcsfs
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import storage

    original_storage_client_init = storage.Client.__init__

    def patched_storage_client_init(self, *args, **kwargs):
        emulator_host = os.getenv("STORAGE_EMULATOR_HOST")
        if emulator_host:
            kwargs["credentials"] = AnonymousCredentials()
            if "project" not in kwargs or not kwargs["project"]:
                kwargs["project"] = "test-project"
        original_storage_client_init(self, *args, **kwargs)

    storage.Client.__init__ = patched_storage_client_init

    original_bucket_get_blob = storage.Bucket.get_blob
    original_makedir = fs_gcsfs._gcsfs.GCSFS.makedir

    # In-memory tracking of directories created during the current process run
    created_dirs = set()

    def patched_makedir(self, path, permissions=None, recreate=False):
        _path = self.validatepath(path)
        _key = self._path_to_dir_key(_path)
        res = original_makedir(self, path, permissions, recreate)
        created_dirs.add(_key)
        return res

    def patched_bucket_get_blob(self, blob_name, client=None, **kwargs):
        blob = original_bucket_get_blob(self, blob_name, client, **kwargs)
        if blob:
            return blob
        if isinstance(blob_name, str) and blob_name.endswith("/"):
            # Case 1: Check in-memory created directories tracking for empty folders
            if blob_name in created_dirs:
                return storage.blob.Blob(name=blob_name, bucket=self)
            for d in created_dirs:
                if d.startswith(blob_name):
                    return storage.blob.Blob(name=blob_name, bucket=self)

            # Case 2: Check prefix search for pre-existing folders containing files
            blobs = list(self.list_blobs(prefix=blob_name, max_results=1))
            if blobs:
                # Return a dummy Blob object so getinfo/isdir is satisfied
                return storage.blob.Blob(name=blob_name, bucket=self)
        return None

    storage.Bucket.get_blob = patched_bucket_get_blob
    fs_gcsfs._gcsfs.GCSFS.makedir = patched_makedir

    if not os.getenv("PORT"):
        for p in ["/import/simple", "/workspace/import/simple", os.getcwd()]:
            if p not in sys.path:
                sys.path.append(p)

        try:
            from util import filesystem
            original_open_dir = filesystem.Dir.open_dir

            def patched_open_dir(self, path):
                full_gcs_path = self.full_path(path)
                if isinstance(full_gcs_path, str) and full_gcs_path.startswith("gs://"):
                    try:
                        gcs_rel_path = full_gcs_path.split("://", 1)[1].split("/", 1)[1]
                        if not gcs_rel_path.endswith("/"):
                            gcs_rel_path += "/"
                        created_dirs.add(gcs_rel_path)
                    except (IndexError, NameError):
                        pass
                return original_open_dir(self, path)

            filesystem.Dir.open_dir = patched_open_dir
        except (ImportError, ModuleNotFoundError):
            pass
except ModuleNotFoundError:
    pass

try:
    for p in ["/workspace/import/simple", os.getcwd()]:
        if p not in sys.path:
            sys.path.append(p)

    from util import dc_client

    def patched_get_property_of_entities(entities, property_name):
        res = {}
        for e in entities:
            if "name" in property_name:
                if e == "country/USA":
                    res[e] = "United States of America"
                else:
                    res[e] = e
            elif "typeOf" in property_name:
                if e.startswith("country/") or e.startswith("geoId/"):
                    res[e] = "Country"
                else:
                    res[e] = e
            else:
                res[e] = e
        return res

    def patched_resolve_entities(
        entities, entity_type=None, property_name="description"
    ):
        res = {}
        for e in entities:
            if e == "country/USA":
                res[e] = "United States of America"
            else:
                res[e] = e
        return res

    def patched_get_entities_of_type(entity_type, next_token=None):
        return {}, ""

    def patched_resolve_entity_type(entity_dcids):
        if len(entity_dcids) == 1:
            e = entity_dcids[0]
            if e.startswith("country/") or e.startswith("geoId/"):
                return "Country"
        return ""

    dc_client.get_property_of_entities = patched_get_property_of_entities
    dc_client.resolve_entities = patched_resolve_entities
    dc_client.get_entities_of_type = patched_get_entities_of_type
    dc_client.resolve_entity_type = patched_resolve_entity_type
except (ImportError, ModuleNotFoundError):
    pass

__version__ = "0.0.0-dev"
