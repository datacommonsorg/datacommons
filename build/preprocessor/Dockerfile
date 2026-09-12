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

# Image for the Data Commons ingestion preprocessor.
#
# Replaces the `datacommons-data` image that was previously built out of the
# website repo from `import/simple` (website/build/cdc_data/Dockerfile). The
# notable difference is dependency installation: the old image pip-installed an
# unlocked `requirements.txt`, this one syncs from the workspace `uv.lock` so
# builds are reproducible.
#
# Build context is the repository root:
#   docker build -f build/preprocessor/Dockerfile -t datacommons-preprocessor .

FROM python:3.12-slim

# Install uv. Pinning version for reproducibility.
COPY --from=ghcr.io/astral-sh/uv:0.9.10 /uv /bin/uv

WORKDIR /app

# Copy the workspace configuration files.
COPY pyproject.toml uv.lock ./

# Copy the workspace members. `uv sync` resolves against the whole workspace, so
# every member listed under [tool.uv.workspace] has to be present even though we
# only install one package.
COPY packages/ ./packages/
COPY tools/ ./tools/

# Install only the preprocessor and its runtime dependencies from the lockfile.
RUN uv sync --frozen --no-dev --package datacommons-preprocessor --no-cache

# Place the virtualenv in the PATH.
ENV PATH="/app/.venv/bin:$PATH"

COPY build/preprocessor/run.sh ./run.sh

# Create a non-root user and switch to it for security.
RUN groupadd -r -g 1001 datacommons-runner \
    && useradd -r -g 1001 -u 1001 datacommons-runner
USER datacommons-runner

ENTRYPOINT ["/bin/bash", "./run.sh"]
