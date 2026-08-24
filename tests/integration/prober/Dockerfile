# Copyright 2026 Google LLC
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

FROM python:3.13-slim

# Copy standalone static binaries for terraform and uv
COPY --from=hashicorp/terraform:1.10 /bin/terraform /bin/terraform
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install system dependencies (ca-certificates, git, google-cloud-cli) and clean up in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    gnupg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && apt-get update && apt-get install -y --no-install-recommends google-cloud-cli \
    && apt-get purge -y --auto-remove gnupg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man

WORKDIR /app

# Environment settings to eliminate build caches and runtime buffering
ARG COMMIT_SHA=unknown
ENV COMMIT_SHA=$COMMIT_SHA \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1

# 1. Copy dependency specifications and workspace packages
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/

# 2. Pre-install dependencies (cached unless dependencies change)
RUN uv sync --frozen || uv sync

# 3. Copy Terraform modules and test harness
COPY infra/ ./infra/
COPY tests/ ./tests/

# Default entrypoint executes the ephemeral prober runner (Provision -> Test -> Destroy)
ENTRYPOINT ["uv", "run", "python", "tests/integration/prober/prober_runner.py"]
