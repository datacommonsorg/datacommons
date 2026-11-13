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

# Prints the test coverage of the lines a pull request changes, with
# diff-cover. Report-only: always exits 0.
#
# Usage: report_changed_lines.sh <report> [<report> ...] [<diff-cover option> ...]
#
# Environment:
#   COVERAGE_BASE_BRANCH  Base branch of the pull request. Empty: not a pull
#                         request, so there's nothing to report.
#   COVERAGE_REMOTE       Repository to fetch the base branch from
#                         (default: origin).
#
# Needs git and diff-cover on PATH.

set -uo pipefail

function skip {
  echo "Changed-line coverage not measured: $1"
  exit 0
}

branch="${COVERAGE_BASE_BRANCH:-}"
[[ -n "$branch" ]] || skip "not a pull request"
command -v diff-cover > /dev/null || skip "diff-cover not installed"
git rev-parse --git-dir > /dev/null 2>&1 || skip "no git checkout"

remote="${COVERAGE_REMOTE:-origin}"
base="refs/remotes/coverage-base/$branch"
if [[ "$(git rev-parse --is-shallow-repository)" == true ]]; then
  # CI checks out only the head commit: deepen both sides until they meet.
  head="$(git rev-parse HEAD)"
  for depth in 100 1000; do
    git fetch -q --no-tags --depth="$depth" "$remote" \
      "+refs/heads/$branch:$base" "$head" \
      || skip "couldn't fetch $branch from $remote"
    git merge-base "$base" HEAD > /dev/null 2>&1 && break
  done
else
  git fetch -q --no-tags "$remote" "+refs/heads/$branch:$base" \
    || skip "couldn't fetch $branch from $remote"
fi
git merge-base "$base" HEAD > /dev/null 2>&1 \
  || skip "no merge-base with $branch"

echo "#### Coverage of lines changed since $branch"
diff-cover "$@" --compare-branch="$base" || skip "diff-cover failed"
