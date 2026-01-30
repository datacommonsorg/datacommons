FROM python:3.12-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy the workspace configuration files
COPY pyproject.toml uv.lock ./

# Copy the package directories
COPY packages/ ./packages/

# Install the dependencies, strictly from the lockfile
RUN uv sync --frozen --no-dev --no-install-project

# Install the project itself
RUN uv sync --frozen --no-dev

# Place the virtualenv in the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the API port
EXPOSE 5000

# Set the entrypoint to the CLI
ENTRYPOINT ["datacommons", "api"]
CMD ["--host", "0.0.0.0", "--port", "5000"]
