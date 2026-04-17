# Stage 1: Build MkDocs site
FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim AS builder

# Install git (required for mkdocs-git-authors-plugin)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create virtual environment
RUN uv venv /app/.venv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (production only), using BuildKit cache to avoid re-downloading
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Copy documentation source
COPY src/ ./src/
COPY mkdocs.yml ./

# Initialize git repo for mkdocs-git-authors-plugin (required even if not using real git history)
RUN git init . && git config user.email "build@localhost" && git config user.name "Build" && git add . && git commit -m "Build commit"

# Set GitPython to quiet mode
ENV GIT_PYTHON_REFRESH=quiet

# Build documentation site
RUN uv run mkdocs build --strict --site-dir /dist

# Stage 2: Serve with nginx
FROM nginxinc/nginx-unprivileged:stable

# Copy built documentation from builder stage
COPY --from=builder /dist /usr/share/nginx/html

# Expose nginx port (unprivileged nginx uses 8080 by default)
EXPOSE 8080

# Use nginx default startup command
CMD ["nginx", "-g", "daemon off;"]
