# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

# Set the working directory in the container
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Copy from the cache instead of linking since it's a separate volume
ENV UV_LINK_MODE=copy

# 1. Install dependencies first (Layer Caching)
# We omit uv.lock bind mount to force fresh resolution on Cloud Build
# (Avoids 401 Unauthorized errors from local private mirror refs)
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

# 2. Copy the rest of the project
COPY . .

# 3. Final installation of the project itself
# Again, no --frozen to allow uv to manage the lock state in this environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

ENV PORT=8080
ENV HOST=0.0.0.0
ENV A2UI_PROTOCOL_VERSION="0.8"
ENV CLOUD_RUN_URL="https://adk2-agent-service-221414075203.europe-west4.run.app"

# Run the application directly from the venv
CMD ["adk2"]
