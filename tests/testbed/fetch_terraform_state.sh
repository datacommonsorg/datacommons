#!/usr/bin/env bash

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

# ==============================================================================
# Backward Compatibility Shim for testbed.sh
# ==============================================================================
# 'fetch_terraform_state.sh' has been renamed to 'testbed.sh' to reflect its
# expanded role in testbed configuration, source switching, and lifecycle management.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Notice: 'fetch_terraform_state.sh' is deprecated and has been renamed to 'testbed.sh'." >&2
echo "Forwarding command to: ${SCRIPT_DIR}/testbed.sh $@" >&2
echo "" >&2

exec "${SCRIPT_DIR}/testbed.sh" "$@"
