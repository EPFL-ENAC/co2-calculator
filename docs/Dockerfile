# Stage 1: Build MkDocs site
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

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

# The git plugins and minify are skipped here (see mkdocs.yml): the build
# context has no git history, so they only produced the build date and a
# fake author while tripling the build time.
ENV MKDOCS_FULL_BUILD=false
# GitPython (pulled in by the git plugins) probes for a git binary at import
# time, before mkdocs reads `enabled`. Quiet keeps the import from raising.
ENV GIT_PYTHON_REFRESH=quiet

# Build documentation site
RUN uv run mkdocs build --strict --site-dir /dist

# Stage 2: Serve with nginx (alpine: the debian variant ships ~100 OS
# packages that dominate CVE scans and are unused for serving static files)
FROM nginxinc/nginx-unprivileged:stable-alpine-slim

# The alpine base lags Alpine's package repo and Trivy blocks the deploy on
# every HIGH it finds there: take every fixed package at build time (#3000).
# Base runs as uid 101 (nginx) — apk needs root.
USER root
RUN apk upgrade --no-cache
USER 101

# Copy built documentation from builder stage
COPY --from=builder /dist /usr/share/nginx/html

# Expose nginx port (unprivileged nginx uses 8080 by default)
EXPOSE 8080

# Use nginx default startup command
CMD ["nginx", "-g", "daemon off;"]
