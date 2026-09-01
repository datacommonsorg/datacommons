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

"""Runtime compatibility patches for Google Cloud client libraries in local emulators.

Automatically imported by Python at interpreter startup when PYTHONPATH points to this directory.
"""

import socket

# Force IPv4 resolution for localhost/loopback in containers without IPv6 support
_orig_getaddrinfo = socket.getaddrinfo


def _patched_getaddrinfo(host, port, family=0, *args, **kwargs):
    if family in (socket.AF_UNSPEC, socket.AF_INET6) and host in (
        "localhost",
        "127.0.0.1",
        "0.0.0.0",  # noqa: S104
    ):
        family = socket.AF_INET
    return _orig_getaddrinfo(host, port, family, *args, **kwargs)


socket.getaddrinfo = _patched_getaddrinfo

import entity_resolution_patch
import gcs_patch
import spanner_patch

__all__ = ["spanner_patch", "gcs_patch", "entity_resolution_patch"]
