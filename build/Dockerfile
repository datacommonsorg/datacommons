FROM python:3.12-slim

# Install uv. Pinning version for reproducibility.
COPY --from=ghcr.io/astral-sh/uv:0.9.10 /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy the workspace configuration files
COPY pyproject.toml uv.lock ./

# Copy the package directories
COPY packages/ ./packages/

# Install the dependencies and the project itself
# uv sync --frozen installs everything from the lockfile.
RUN uv sync --frozen --no-dev

# Place the virtualenv in the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Create a non-root user and switch to it for security
RUN groupadd -r datacommons-runner && useradd -r -g datacommons-runner datacommons-runner
USER datacommons-runner

# Expose the API port
EXPOSE 5000

# Set the entrypoint to the CLI
ENTRYPOINT ["datacommons", "api"]
CMD ["start", "--host", "0.0.0.0", "--port", "5000"]
