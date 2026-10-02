# Stage 1: Build the Zensical site
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
# Every top-level .py, not a hand-listed set: gen_indexes.py and
# check_links.py are both build-time code, and the next one added must not
# silently break this image.
COPY zensical.toml *.py ./

# Same steps as `make build-docs`: a dead link fails the image build.
RUN uv run python gen_indexes.py \
    && uv run zensical build --clean --strict \
    && uv run python check_links.py site

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
COPY --from=builder /app/site /usr/share/nginx/html

# Expose nginx port (unprivileged nginx uses 8080 by default)
EXPOSE 8080

# Use nginx default startup command
CMD ["nginx", "-g", "daemon off;"]
