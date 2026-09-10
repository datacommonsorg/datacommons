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

"""Fake GCS emulator compatibility patch.

1. Injects AnonymousCredentials when STORAGE_EMULATOR_HOST is set.
2. Patches directory-blob lookup in google-cloud-storage and fs_gcsfs to handle
   virtual directory blobs in fake-gcs-server.
"""

import os

try:
    import fs_gcsfs
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import storage

    HAS_GCS = True
except (ImportError, ModuleNotFoundError):
    HAS_GCS = False

if HAS_GCS:
    original_storage_client_init = storage.Client.__init__

    def patched_storage_client_init(self, *args, **kwargs):
        emulator_host = os.getenv("STORAGE_EMULATOR_HOST")
        if emulator_host:
            kwargs["credentials"] = AnonymousCredentials()
            if not kwargs.get("project"):
                kwargs["project"] = "test-project"
        original_storage_client_init(self, *args, **kwargs)

    storage.Client.__init__ = patched_storage_client_init

    original_bucket_get_blob = storage.Bucket.get_blob
    original_makedir = fs_gcsfs._gcsfs.GCSFS.makedir

    created_dirs = set()

    def patched_makedir(self, path, permissions=None, recreate=False):
        path_val = self.validatepath(path)
        dir_key = self._path_to_dir_key(path_val)
        res = original_makedir(self, path, permissions, recreate)
        created_dirs.add(dir_key)
        return res

    def patched_bucket_get_blob(self, blob_name, client=None, **kwargs):
        blob = original_bucket_get_blob(self, blob_name, client, **kwargs)
        if (
            not blob
            and isinstance(blob_name, str)
            and blob_name.endswith("/")
            and (
                any(d.startswith(blob_name) for d in created_dirs)
                or next(self.list_blobs(prefix=blob_name, max_results=1), None)
            )
        ):
            return storage.blob.Blob(name=blob_name, bucket=self)
        return blob

    storage.Bucket.get_blob = patched_bucket_get_blob
    fs_gcsfs._gcsfs.GCSFS.makedir = patched_makedir
