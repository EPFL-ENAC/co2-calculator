# Stage 1: Build MkDocs site
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

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
# Every top-level .py, not a hand-listed set: gen_indexes.py and hooks.py
# are both build-time code, and the next one added must not silently
# break this image the way hooks.py did.
COPY mkdocs.yml *.py ./

# Initialize git repo for mkdocs-git-authors-plugin (required even if not using real git history)
RUN git init . && git config user.email "build@localhost" && git config user.name "Build" && git add . && git commit -m "Build commit"

# Set GitPython to quiet mode
ENV GIT_PYTHON_REFRESH=quiet

# Build documentation site
RUN uv run mkdocs build --strict --site-dir /dist

# Stage 2: Serve with nginx (alpine: the debian variant ships ~100 OS
# packages that dominate CVE scans and are unused for serving static files)
FROM nginxinc/nginx-unprivileged:stable-alpine-slim

# CVE-2026-14456: openssl < 3.5.8-r0 in the alpine base; drop once the base
# image ships the fix (apk upgrade becomes a no-op then). Base runs as
# uid 101 (nginx) — apk needs root.
USER root
RUN apk upgrade --no-cache libcrypto3 libssl3
USER 101

# Copy built documentation from builder stage
COPY --from=builder /dist /usr/share/nginx/html

# Expose nginx port (unprivileged nginx uses 8080 by default)
EXPOSE 8080

# Use nginx default startup command
CMD ["nginx", "-g", "daemon off;"]
