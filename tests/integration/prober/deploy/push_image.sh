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

# Builds the prober image from the current checkout and pushes it with a dev tag,
# for testing a branch on the prober before merging. It does not change :latest
# or the dcp-prober job. See "Testing a Branch Image on the Prober" in README.md.
#
# Usage: ./tests/integration/prober/deploy/push_image.sh <dev-tag>

set -euo pipefail

IMAGE_TAG="${1:-}"

if [[ -z "${IMAGE_TAG}" ]]; then
  echo "Usage: $0 <dev-tag>" >&2
  exit 1
fi

# 'latest' is published by the deploy-dcp-prober-on-main trigger. Never
# overwrite it from a dev build.
if [[ "${IMAGE_TAG}" == "latest" ]]; then
  echo "Image tag 'latest' is reserved for CI. Use a different tag for dev builds." >&2
  exit 1
fi

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${DEPLOY_DIR}/../../../.." && pwd)"
COMMIT_SHA="$(git -C "${REPO_ROOT}" rev-parse HEAD)"

set -x
gcloud builds submit "${REPO_ROOT}" \
  --project=datcom-ci \
  --config="${DEPLOY_DIR}/cloudbuild.yaml" \
  --substitutions="_TAG=${IMAGE_TAG},_VERSION=${IMAGE_TAG},_COMMIT_SHA=${COMMIT_SHA},_UPDATE_JOB=false"
