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

set -eo pipefail

NEW_VERSION="$1"
if [ -z "$NEW_VERSION" ]; then
  echo "Usage: $0 <NEW_VERSION>"
  exit 1
fi

OLD_VERSION=$(tr -d '[:space:]' < VERSION)
echo "Applying version bump: '$OLD_VERSION' -> '$NEW_VERSION'..."

# 1. Update root VERSION file
echo "$NEW_VERSION" > VERSION

# 2. Update subpackage VERSION files
for pkg in packages/*; do
  if [ -d "$pkg" ]; then
    echo "Updating $pkg/VERSION to $NEW_VERSION"
    echo "$NEW_VERSION" > "$pkg/VERSION"
  fi
done

# 3. Update __init__.py files across all packages
python3 -c "import glob, re; [open(f, 'w').write(re.sub(r'^__version__ = [\"\'].*[\"\']', '__version__ = \"'\"$NEW_VERSION\"'\"', content, flags=re.MULTILINE)) for f in glob.glob('packages/*/datacommons_*/__init__.py') for content in [open(f, 'r').read()]]"

# 4. Update Terraform variables (dcp_version default)
find infra/dcp -type f -name "*.tf" -exec sed -i "s/$OLD_VERSION/$NEW_VERSION/g" {} +

# 5. Lock datacommons-admin dependency requirement in datacommons-cli/pyproject.toml
python3 -c "import re, sys; p='packages/datacommons-cli/pyproject.toml'; content = open(p).read(); updated, count = re.subn(r'\"datacommons-admin[^\"]*\"', f'\"datacommons-admin>=$NEW_VERSION\"', content); open(p, 'w').write(updated) if count else sys.exit('Error: datacommons-admin dependency not found or updated in packages/datacommons-cli/pyproject.toml')"

echo "Successfully applied version bump to '$NEW_VERSION'."
