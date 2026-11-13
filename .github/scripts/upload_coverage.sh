#!/bin/bash
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

# Uploads test coverage reports to Codacy. Report-only: always exits 0.
#
# Usage: upload_coverage.sh <report>[:<prefix>] [<report>[:<prefix>] ...]
#
# Codacy needs file paths relative to the repository root. <prefix> is added
# to the paths in a report whose paths are relative to a subdirectory (e.g.
# JaCoCo's, which are relative to the module's source root).
#
# Environment:
#   COMMIT_SHA             Commit the reports belong to.
#   CODACY_DEFAULT_BRANCH  The only branch that gets coverage (default: master).
#   _BASE_BRANCH           Base branch of a pull request. Empty for pushes.
#   BRANCH_NAME            Branch of a push.
#   CODACY_PROJECT_TOKEN   Codacy project token. If empty, it's read from
#                          Secret Manager when CODACY_SECRET_NAME is set.
#   CODACY_SECRET_NAME     Secret that holds the token.
#   CODACY_SECRET_PROJECT  Project of that secret (default: datcom-ci).

set -uo pipefail

readonly REPORTER_VERSION="14.1.3"
readonly REPORTER_SHA512="73a6c93fc5db509fd0423d6e545759c3f61d8360ee12054e32a9277daab6add0da6c6639248f6ed6c0042366440293ebc0b6144325aef52c5d3d4b230d65eb17"
readonly REPORTER_URL="https://github.com/codacy/codacy-coverage-reporter/releases/download/${REPORTER_VERSION}/codacy-coverage-reporter-linux"

function skip {
  echo "Codacy upload skipped: $1"
  exit 0
}

function fail {
  echo "Codacy upload failed (report-only): $1"
  exit 0
}

default_branch="${CODACY_DEFAULT_BRANCH:-master}"
branch="${_BASE_BRANCH:-${BRANCH_NAME:-}}"
[[ "$branch" == "$default_branch" ]] \
  || skip "branch ${branch:-(none)} is not $default_branch"
[[ -n "${COMMIT_SHA:-}" ]] || skip "no commit SHA"

if [[ -z "${CODACY_PROJECT_TOKEN:-}" && -n "${CODACY_SECRET_NAME:-}" ]]; then
  CODACY_PROJECT_TOKEN="$(gcloud secrets versions access latest \
    --secret="$CODACY_SECRET_NAME" \
    --project="${CODACY_SECRET_PROJECT:-datcom-ci}" 2> /dev/null)" \
    || CODACY_PROJECT_TOKEN=""
fi
[[ -n "${CODACY_PROJECT_TOKEN:-}" ]] || skip "no token"
# The reporter reads the token from the environment, never from its arguments.
export CODACY_PROJECT_TOKEN

reports=()
for report in "$@"; do
  if [[ -s "${report%%:*}" ]]; then
    reports+=("$report")
  fi
done
(( ${#reports[@]} > 0 )) || skip "no coverage reports"

reporter="$(mktemp)"
trap 'rm -f "$reporter"' EXIT
curl -fsSL --retry 3 -o "$reporter" "$REPORTER_URL" \
  || skip "reporter download failed"
echo "$REPORTER_SHA512  $reporter" | sha512sum --check --status \
  || skip "reporter checksum mismatch"
chmod +x "$reporter"

# Uploads one <report>[:<prefix>]; any other arguments go to the reporter.
function upload_report {
  local report="${1%%:*}" prefix=()
  if [[ "$1" == *:* ]]; then
    prefix=(--prefix "${1#*:}")
  fi
  "$reporter" report "${@:2}" --commit-uuid "$COMMIT_SHA" -r "$report" \
    "${prefix[@]}" || fail "report $report"
}

if (( ${#reports[@]} == 1 )); then
  upload_report "${reports[0]}"
else
  for report in "${reports[@]}"; do
    upload_report "$report" --partial
  done
  "$reporter" final --commit-uuid "$COMMIT_SHA" || fail "final"
fi
